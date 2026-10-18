"""
Coordinador de la configuración de Claude: cuenta, modelo, esfuerzo, respaldo y tiempo máximo.

Es la fuente única del `ClaudeModelConfig` que usa el Agente: cada cambio se guarda en
`app_settings.json` y se avisa. Comprobar la cuenta corre en su propio hilo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.claude_account import AccountStatus, describe
from core.claude_model import ClaudeModelConfig, clean_account
from paths import CLAUDE_ACCOUNTS_DIR, ROOT
from services.service_claude import resolve_profile
from services.service_claude_account import (
    config_dir_for,
    login_command,
    prepare_account_dir,
    read_status,
)
from workers.worker_account import AccountWorker, StatusReader
from workers.worker_runner import RequestSequence, start_worker, stop_thread

logger = logging.getLogger(__name__)

# (clave, nombre en el botón, ayuda); los tiempos son del banco de la CLI.
CLAUDE_MODELS = (
    ("haiku", "haiku", "El más barato; primer texto en ~2 s"),
    ("sonnet", "sonnet", "Equilibrado; primer texto en ~2 s"),
    ("opus", "opus", "El más capaz; primer texto en ~3 s"),
)
EFFORTS = (
    ("", "por defecto", "El nivel que trae el modelo"),
    ("low", "low", "Responde más rápido, razona menos"),
    ("medium", "medium", ""),
    ("high", "high", ""),
    ("xhigh", "xhigh", ""),
    ("max", "max", "Razona lo más posible; tarda más"),
)
FALLBACKS = ("", "haiku", "sonnet", "opus")
TIMEOUTS_S = (60, 120, 300)
CLOSE_TIMEOUT_MS = 3_000


class ClaudeSettings(QObject):
    """
    Signals
    -------
    config_changed(object) -> el `ClaudeModelConfig` nuevo, ya guardado.
    account_checked(dict)  -> `text`, `level` ("ok", "warning", "error" o "busy") y
                              `login` (la orden para iniciar sesión, o "").
    """

    config_changed = Signal(object)
    account_checked = Signal(dict)

    def __init__(
        self,
        config: ClaudeModelConfig | None = None,
        save_config: Callable[[ClaudeModelConfig], object] | None = None,
        status_reader: StatusReader = read_status,
        accounts_dir: Path = CLAUDE_ACCOUNTS_DIR,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config or ClaudeModelConfig()
        self._save_config = save_config
        self._reader = status_reader
        self._accounts_dir = accounts_dir
        self._requests = RequestSequence()
        self._worker: AccountWorker | None = None
        self._thread: QThread | None = None

    # -- Pedidos de la vista -----------------------------------

    @property
    def profile_path(self) -> Path:
        return resolve_profile()

    @property
    def profile_text(self) -> str:
        """El perfil en uso, relativo al proyecto si está dentro."""
        path = self.profile_path
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)

    def config_dir(self) -> Path | None:
        return config_dir_for(self.config.account, self._accounts_dir)

    def set_model(self, model: str) -> None:
        self._update(model=model)

    def set_effort(self, effort: str) -> None:
        self._update(effort=effort)

    def set_fallback(self, model: str) -> None:
        self._update(fallback_model=model)

    def set_timeout(self, seconds: int) -> None:
        self._update(timeout_s=seconds)

    def set_account(self, text: str) -> bool:
        """Cambia la cuenta y la comprueba; False si no parece un correo."""
        account = clean_account(text)
        if text.strip() and not account:
            self.account_checked.emit(
                {"text": f"«{text.strip()}» no parece un correo", "level": "error", "login": ""}
            )
            return False
        self._update(account=account)
        self.check()
        return True

    def check(self) -> None:
        if self._thread is not None:
            return
        self.account_checked.emit(
            {"text": "Comprobando la cuenta...", "level": "busy", "login": ""}
        )
        worker = self._worker = AccountWorker(
            reader=self._reader,
            executable=self.config.executable,
            config_dir=self.config_dir(),
            request_id=self._requests.next(),
        )
        self._thread = start_worker(
            self, worker, on_done=self.on_status, on_cleared=self._clear_refs
        )

    def show_status(self, status: AccountStatus) -> None:
        """Avisa el estado; sin sesión o con otra cuenta, prepara la orden de inicio."""
        text, level = describe(status, self.config.account)
        login = ""
        if level == "warning":
            folder = None
            if self.config.account:
                # Nunca se inicia sesión de otra cuenta sobre la de siempre (~/.claude).
                folder = prepare_account_dir(self.config.account, self._accounts_dir)
            login = login_command(self.config.executable, self.config.account, folder)
        self.account_checked.emit({"text": text, "level": level, "login": login})

    def close(self) -> None:
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker ------------------------------------

    @Slot(dict)
    def on_status(self, payload: dict) -> None:
        if self._requests.is_current(payload):
            self.show_status(payload["status"])

    # -- Internos ----------------------------------------------

    def _update(self, **changes) -> None:
        new = ClaudeModelConfig.from_dict({**self.config.to_dict(), **changes})
        if new == self.config:
            return
        self.config = new
        if self._save_config is not None:
            self._save_config(new)
        self.config_changed.emit(new)

    def _clear_refs(self) -> None:
        self._worker = None
        self._thread = None
