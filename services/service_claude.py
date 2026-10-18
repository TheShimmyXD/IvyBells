"""
Servicio de Claude por la CLI de Claude Code (`claude -p`), sin clave de API.

Lanza la orden aislada de `ClaudeModelConfig.command`, le pasa el prompt por stdin y lee
el stream: cada trozo de texto se entrega en cuanto llega. Respeta el tiempo máximo y se
cancela terminando el proceso (y sus hijos). `ScriptedClaude` responde con un guion fijo,
para las pruebas y las capturas: nunca gasta el cupo del autor.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from core.claude_model import ClaudeModelConfig
from core.claude_stream import Finished, TextDelta, parse_line
from paths import AGENT_PROFILE, AGENT_PROFILE_LOCAL, AGENT_WORKDIR

logger = logging.getLogger(__name__)

TextCallback = Callable[[str], None]
# Cada cuánto se revisa si se pidió cancelar o se pasó el tiempo.
_WATCH_S = 0.1
_KILL_GRACE_S = 2.0


class ClaudeError(RuntimeError):
    """La CLI no respondió bien; el mensaje va en una línea para la ventana."""


class ClaudeCancelled(Exception):
    """Se canceló a pedido del autor."""


class ClaudeService(Protocol):
    def ask(self, prompt: str, on_text: TextCallback, cancel: threading.Event) -> Finished:
        """Envía el prompt y llama `on_text` con cada trozo; devuelve el resultado final."""


def resolve_profile() -> Path:
    """El perfil de la empresa si existe; si no, el de ejemplo."""
    return AGENT_PROFILE_LOCAL if AGENT_PROFILE_LOCAL.exists() else AGENT_PROFILE


class ClaudeCli:
    """`claude -p` aislado, en una carpeta vacía fuera del proyecto."""

    def __init__(
        self,
        config: ClaudeModelConfig,
        profile: Path | None = None,
        workdir: Path = AGENT_WORKDIR,
    ) -> None:
        self.config = config
        self.profile = profile or resolve_profile()
        self.workdir = workdir

    def ask(self, prompt: str, on_text: TextCallback, cancel: threading.Event) -> Finished:
        self.workdir.mkdir(parents=True, exist_ok=True)
        command = self.config.command(self.profile)
        logger.info("Enviando a Claude (%s), %d caracteres", self.config.model, len(prompt))
        try:
            process = subprocess.Popen(
                command,
                cwd=self.workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                # Grupo propio: al cancelar se terminan también los hijos de la CLI.
                start_new_session=True,
            )
        except OSError as exc:
            raise ClaudeError(f"No se pudo lanzar '{self.config.executable}': {exc}") from exc

        stopped: dict[str, str] = {}
        watcher = threading.Thread(target=self._watch, args=(process, cancel, stopped), daemon=True)
        watcher.start()
        finished = None
        try:
            assert process.stdin is not None and process.stdout is not None
            try:
                process.stdin.write(prompt)
                process.stdin.close()
            except BrokenPipeError:
                # La CLI se cerró antes de leer el prompt; su error sale en stderr.
                logger.warning("La CLI de Claude cerró la entrada antes de leer el prompt")
            for line in process.stdout:
                update = parse_line(line)
                if isinstance(update, TextDelta):
                    on_text(update.text)
                elif isinstance(update, Finished):
                    finished = update
            process.wait()
        finally:
            stopped.setdefault("reason", "done")
            watcher.join()
            if process.poll() is None:
                _terminate(process)
        stderr = process.stderr.read().strip() if process.stderr else ""
        return self._outcome(stopped["reason"], finished, process.returncode, stderr)

    def _watch(self, process: subprocess.Popen, cancel: threading.Event, stopped: dict) -> None:
        deadline = time.monotonic() + self.config.timeout_s
        while process.poll() is None and "reason" not in stopped:
            if cancel.is_set() or time.monotonic() > deadline:
                stopped["reason"] = "cancel" if cancel.is_set() else "timeout"
                _terminate(process)
                return
            cancel.wait(_WATCH_S)

    def _outcome(
        self, reason: str, finished: Finished | None, code: int | None, stderr: str
    ) -> Finished:
        if reason == "cancel":
            raise ClaudeCancelled()
        if reason == "timeout":
            raise ClaudeError(f"Claude no respondió en {self.config.timeout_s} s")
        if finished is None:
            detail = stderr.splitlines()[-1] if stderr else f"código de salida {code}"
            raise ClaudeError(f"La CLI de Claude terminó sin respuesta: {detail}")
        if finished.is_error:
            raise ClaudeError(finished.text or "Claude devolvió un error")
        logger.info(
            "Respuesta de Claude: %d caracteres, primer texto %s ms, total %s ms",
            len(finished.text),
            finished.ttft_ms,
            finished.duration_ms,
        )
        return finished


def _terminate(process: subprocess.Popen) -> None:
    """SIGTERM al grupo del proceso y, si no se va, SIGKILL."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            process.wait(_KILL_GRACE_S)
            return
        except subprocess.TimeoutExpired:
            continue


class ScriptedClaude:
    """
    Responde con trozos fijos, con una pausa entre trozos (pruebas y capturas).

    Con `error` falla después de los trozos; atiende la cancelación entre trozos.
    """

    def __init__(self, chunks: Sequence[str], pause_s: float = 0.0, error: str = "") -> None:
        self.chunks = list(chunks)
        self.pause_s = pause_s
        self.error = error
        self.prompts: list[str] = []

    def ask(self, prompt: str, on_text: TextCallback, cancel: threading.Event) -> Finished:
        self.prompts.append(prompt)
        for chunk in self.chunks:
            if cancel.wait(self.pause_s) if self.pause_s else cancel.is_set():
                raise ClaudeCancelled()
            on_text(chunk)
        if self.error:
            raise ClaudeError(self.error)
        return Finished("".join(self.chunks), False)
