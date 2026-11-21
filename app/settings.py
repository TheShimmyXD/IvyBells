"""
Configuración de Claude: cuenta, modelo, esfuerzo, respaldo y tiempo máximo.

Es la fuente única del `ClaudeModelConfig` que usan el Agente y el chat: cada cambio se
guarda en `app_settings.json` y se avisa. Lleva también los perfiles (`profiles`) y el
contexto (`context`) del agente. Comprobar la cuenta corre en su propio hilo.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.background import Post, call_now, ignore, join, start_task
from app.claude_ask import RequestSequence
from app.context import ContextLibrary
from app.profiles import ProfileLibrary
from domain.claude.claude_account import AccountStatus, describe
from domain.claude.claude_model import ClaudeModelConfig, clean_account
from paths import CLAUDE_ACCOUNTS_DIR
from services.service_claude_account import (
    config_dir_for,
    login_command,
    prepare_account_dir,
    read_status,
)

logger = logging.getLogger(__name__)

StatusReader = Callable[[str, Path | None], AccountStatus]

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
CLOSE_TIMEOUT_S = 3.0


@dataclass
class SettingsListeners:
    """
    Avisos de la configuración a su dueño, siempre en el hilo dueño. Por defecto no hacen nada.

    config(ClaudeModelConfig) -> el modelo nuevo, ya guardado.
    account(dict)             -> `text`, `level` ("ok", "warning", "error" o "busy") y
                                 `login` (la orden para iniciar sesión, o "").
    """

    config: Callable[[ClaudeModelConfig], None] = ignore
    account: Callable[[dict], None] = ignore


class ClaudeOptions:
    """Caso de uso de la configuración de Claude; se usa desde un solo hilo (el dueño)."""

    def __init__(
        self,
        config: ClaudeModelConfig | None = None,
        save_config: Callable[[ClaudeModelConfig], object] | None = None,
        status_reader: StatusReader = read_status,
        accounts_dir: Path = CLAUDE_ACCOUNTS_DIR,
        profiles: ProfileLibrary | None = None,
        context: ContextLibrary | None = None,
    ) -> None:
        self.config = config or ClaudeModelConfig()
        self.profiles = profiles or ProfileLibrary()
        self.context = context or ContextLibrary()
        self._save_config = save_config
        self._reader = status_reader
        self._accounts_dir = accounts_dir
        self._requests = RequestSequence()
        self._thread: threading.Thread | None = None
        self.listeners = SettingsListeners()
        self._post: Post = call_now

    def attach(self, post: Post, listeners: SettingsListeners) -> None:
        """Fija el hilo dueño y quién recibe los avisos; la puerta lo llama una vez al armarse."""
        self._post = post
        self.listeners = listeners

    def is_busy(self) -> bool:
        return self._thread is not None

    # -- Pedidos del dueño -------------------------------------

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
            self.listeners.account(
                {"text": f"«{text.strip()}» no parece un correo", "level": "error", "login": ""}
            )
            return False
        self._update(account=account)
        self.check()
        return True

    def check(self) -> None:
        """Lee el estado de la cuenta en un hilo; el resultado llega por `account`."""
        if self._thread is not None:
            return
        self.listeners.account({"text": "Comprobando la cuenta...", "level": "busy", "login": ""})
        request_id = self._requests.next()
        reader, executable, folder = self._reader, self.config.executable, self.config_dir()
        self._thread = start_task(
            lambda: reader(executable, folder),
            lambda status, error: self.on_status(request_id, status, error),
            self._post,
            "ivybells-account",
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
        self.listeners.account({"text": text, "level": level, "login": login})

    def close(self, timeout_s: float = CLOSE_TIMEOUT_S) -> None:
        join(self._thread, timeout_s)
        self.context.close(timeout_s)

    # -- Aviso del hilo (ya en el hilo dueño) ------------------

    def on_status(self, request_id: int, status: AccountStatus | None, error: str) -> None:
        self._thread = None
        if not self._requests.is_current({"_request_id": request_id}):
            return
        if status is None:
            # No se pudo leer el estado de la cuenta (el motivo ya está en el log).
            status = AccountStatus(False, error=error or "sin respuesta")
        self.show_status(status)

    # -- Internos ----------------------------------------------

    def _update(self, **changes) -> None:
        new = ClaudeModelConfig.from_dict({**self.config.to_dict(), **changes})
        if new == self.config:
            return
        self.config = new
        if self._save_config is not None:
            self._save_config(new)
        self.listeners.config(new)
