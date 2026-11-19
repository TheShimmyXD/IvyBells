"""
Un envío a Claude fuera del hilo dueño: lo comparten el Agente y el chat.

`ClaudeAsk` corre `service.ask` en el hilo que lo llama y avisa por callbacks.
`AskSlot` lleva uno a la vez en su propio `threading.Thread` y entrega cada aviso al hilo
dueño con `post`, así que el Agente y el chat cambian su estado en un solo hilo.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.live import Post
from domain.claude.claude_model import ClaudeModelConfig
from domain.transcription.live_view import LiveTranscript
from services.service_claude import ClaudeCancelled, ClaudeCli, ClaudeError, ClaudeService

logger = logging.getLogger(__name__)

# Recibe el modelo y el system prompt; devuelve el servicio que hace el envío.
ServiceFactory = Callable[[ClaudeModelConfig, str], ClaudeService]


def claude_cli(config: ClaudeModelConfig, system_prompt: str) -> ClaudeService:
    """El servicio de siempre: la CLI `claude -p` del autor."""
    return ClaudeCli(config, system_prompt)


def _ignore(*_args: object) -> None:
    pass


class LiveText(Protocol):
    """Lo que el Agente y el chat leen de la escucha en vivo."""

    @property
    def transcript(self) -> LiveTranscript: ...

    @property
    def closed_sources(self) -> set[str]: ...


class _Profiles(Protocol):
    def system_prompt(self, context: str) -> str: ...


class _Context(Protocol):
    def text(self) -> str: ...


class ClaudeSetup(Protocol):
    """Lo que el Agente y el chat leen de la configuración: modelo, perfiles y contexto."""

    @property
    def config(self) -> ClaudeModelConfig: ...

    @property
    def profiles(self) -> _Profiles: ...

    @property
    def context(self) -> _Context: ...


class RequestSequence:
    """
    Secuencia de solicitudes para descartar respuestas viejas.

    Cada envío pide `next()` y lo pasa como `request_id`; el envío lo devuelve en el
    payload como `_request_id`. Si mientras tanto se lanzó otro, `is_current()` devuelve
    False y la respuesta se ignora.
    """

    def __init__(self) -> None:
        self._current = 0

    @property
    def current(self) -> int:
        return self._current

    def next(self) -> int:
        self._current += 1
        return self._current

    def is_current(self, payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        return int(payload.get("_request_id", 0)) == self._current


@dataclass(frozen=True)
class AskCallbacks:
    """
    Avisos de un envío.

    text(str)      -> un trozo de la respuesta, en cuanto llega.
    failed(str)    -> motivo de la falla, en una línea.
    finished(dict) -> siempre al final: `_request_id`, `answer`, `cancelled` y `usage`.
    """

    text: Callable[[str], None] = _ignore
    failed: Callable[[str], None] = _ignore
    finished: Callable[[dict], None] = _ignore


class ClaudeAsk:
    """Envía un prompt a Claude y entrega la respuesta por partes; corre en el hilo de `run()`."""

    def __init__(
        self,
        *,
        service: ClaudeService,
        prompt: str,
        cancel_event: threading.Event,
        request_id: int,
        callbacks: AskCallbacks,
    ) -> None:
        self._service = service
        self._prompt = prompt
        self._cancel = cancel_event
        self._request_id = request_id
        self._callbacks = callbacks

    def run(self) -> None:
        callbacks = self._callbacks
        answer = ""
        usage = None
        cancelled = False
        try:
            finished = self._service.ask(self._prompt, callbacks.text, self._cancel)
            answer, usage = finished.text, finished.usage
        except ClaudeCancelled:
            cancelled = True
            logger.info("Envío a Claude cancelado")
        except ClaudeError as exc:
            logger.warning("Claude falló: %s", exc)
            callbacks.failed(str(exc))
        except Exception as exc:
            # Frontera del hilo: sin esto el dueño se queda esperando para siempre.
            logger.exception("El envío a Claude falló")
            callbacks.failed(str(exc) or type(exc).__name__)
        finally:
            callbacks.finished(
                {
                    "_request_id": self._request_id,
                    "answer": answer,
                    "cancelled": cancelled,
                    "usage": usage,
                }
            )


class AskSlot:
    """
    Un envío a Claude a la vez, en su propio hilo.

    Los avisos llegan al hilo dueño por `post`; `finished` solo si el envío sigue siendo
    el vigente, y después `cleared`, cuando el hueco ya quedó libre.
    """

    def __init__(self) -> None:
        self.requests = RequestSequence()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        """Hay un envío corriendo o cerrándose (cancelado pero sin terminar)."""
        return self._thread is not None

    def launch(
        self,
        service: ClaudeService,
        prompt: str,
        post: Post,
        callbacks: AskCallbacks,
        on_cleared: Callable[[], None] = _ignore,
    ) -> None:
        self._cancel = threading.Event()

        def finished(payload: dict) -> None:
            def task() -> None:
                if self.requests.is_current(payload):
                    callbacks.finished(payload)
                self._thread = None
                on_cleared()

            post(task)

        run = ClaudeAsk(
            service=service,
            prompt=prompt,
            cancel_event=self._cancel,
            request_id=self.requests.next(),
            callbacks=AskCallbacks(
                text=lambda chunk: post(lambda: callbacks.text(chunk)),
                failed=lambda message: post(lambda: callbacks.failed(message)),
                finished=finished,
            ),
        )
        # daemon: si la CLI se cuelga, cerrar la app no espera más que el tiempo de `close`.
        self._thread = threading.Thread(target=run.run, name="ivybells-claude", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def close(self, timeout_s: float) -> None:
        """Cancela el envío en curso y espera a su hilo como máximo `timeout_s`."""
        self._cancel.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout_s)
            if thread.is_alive():
                logger.warning("El envío a Claude no terminó en %.0f s; se cierra igual", timeout_s)
