"""
Adaptador Qt de la configuración de Claude (`app.settings.ClaudeOptions`).

La vista solo habla con él. Lleva los adaptadores de los perfiles (`profiles`) y del
contexto (`context`); el resultado de comprobar la cuenta llega de su hilo por `post` y
sale como señal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.settings import ClaudeOptions, SettingsListeners, StatusReader
from domain.claude.claude_account import AccountStatus
from domain.claude.claude_model import ClaudeModelConfig
from entrypoints.ui_qt.coordinators.coordinator_context import AgentContext
from entrypoints.ui_qt.coordinators.coordinator_profiles import AgentProfiles


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
    # Tarea que llega del hilo de la cuenta: Qt la pone en cola y la corre en este hilo.
    _posted = Signal(object)

    def __init__(
        self,
        config: ClaudeModelConfig | None = None,
        save_config: Callable[[ClaudeModelConfig], object] | None = None,
        status_reader: StatusReader | None = None,
        accounts_dir: Path | None = None,
        profiles: AgentProfiles | None = None,
        context: AgentContext | None = None,
        parent: QObject | None = None,
        *,
        options: ClaudeOptions | None = None,
    ) -> None:
        super().__init__(parent)
        if options is None:
            extra: dict = {}
            if status_reader is not None:
                extra["status_reader"] = status_reader
            if accounts_dir is not None:
                extra["accounts_dir"] = accounts_dir
            options = ClaudeOptions(
                config,
                save_config,
                profiles=profiles.library if profiles else None,
                context=context.library if context else None,
                **extra,
            )
        self.options = options
        self.profiles = profiles or AgentProfiles(library=options.profiles, parent=self)
        self.context = context or AgentContext(library=options.context, parent=self)
        self._posted.connect(self._run_posted)
        options.attach(
            self._posted.emit,
            SettingsListeners(config=self.config_changed.emit, account=self.account_checked.emit),
        )

    # -- Lo que lee la vista -----------------------------------

    @property
    def config(self) -> ClaudeModelConfig:
        return self.options.config

    def config_dir(self) -> Path | None:
        return self.options.config_dir()

    def is_busy(self) -> bool:
        return self.options.is_busy()

    # -- Pedidos de la vista -----------------------------------

    def set_model(self, model: str) -> None:
        self.options.set_model(model)

    def set_effort(self, effort: str) -> None:
        self.options.set_effort(effort)

    def set_fallback(self, model: str) -> None:
        self.options.set_fallback(model)

    def set_timeout(self, seconds: int) -> None:
        self.options.set_timeout(seconds)

    def set_account(self, text: str) -> bool:
        return self.options.set_account(text)

    def check(self) -> None:
        self.options.check()

    def show_status(self, status: AccountStatus) -> None:
        self.options.show_status(status)

    def close(self) -> None:
        self.options.close()

    # -- Internos ----------------------------------------------

    @Slot(object)
    def _run_posted(self, task: Callable[[], None]) -> None:
        task()
