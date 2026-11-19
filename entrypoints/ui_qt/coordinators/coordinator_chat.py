"""
Adaptador Qt del chat propio del autor (`app.chat.ChatAssistant`).

La vista solo habla con él. La orquestación vive en `app/`; aquí se pasan los avisos del
hilo del envío al hilo de la ventana y se convierten en señales.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from app.chat import ChatAssistant, ChatListeners, ChatTurn
from app.claude_ask import ServiceFactory, claude_cli
from domain.agent.chat_prompt import DEFAULT_CHAT_EFFORT, DEFAULT_CHAT_MODEL
from domain.claude.claude_model import ClaudeModelConfig
from entrypoints.ui_qt.coordinators.coordinator_config import ClaudeSettings
from entrypoints.ui_qt.coordinators.coordinator_live import LiveCoordinator

__all__ = ["ChatCoordinator", "ChatTurn"]


class ChatCoordinator(QObject):
    """
    Signals
    -------
    turns_changed()          -> cambió la lista de peticiones o la respuesta en curso.
    sending_changed(bool)    -> empezó o terminó un envío.
    config_changed(object)   -> el `ClaudeModelConfig` del chat (modelo, esfuerzo o cuenta).
    """

    turns_changed = Signal()
    sending_changed = Signal(bool)
    config_changed = Signal(object)
    # Tarea que llega del hilo del envío: Qt la pone en cola y la corre en este hilo.
    _posted = Signal(object)

    # Las capturas lo cambian por uno que no lanza la CLI.
    assistant_class: type[ChatAssistant] = ChatAssistant

    def __init__(
        self,
        live: LiveCoordinator,
        settings: ClaudeSettings,
        model: str = DEFAULT_CHAT_MODEL,
        effort: str = DEFAULT_CHAT_EFFORT,
        remember: Callable[[str, object], object] | None = None,
        service_factory: ServiceFactory = claude_cli,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.live = live
        self.settings = settings
        assistant = self.assistant = self.assistant_class(
            live, settings, model, effort, remember, service_factory, clock
        )
        self._posted.connect(self._run_posted)
        assistant.attach(
            self._posted.emit,
            ChatListeners(
                turns=self.turns_changed.emit,
                sending=self.sending_changed.emit,
                config=self.config_changed.emit,
            ),
        )
        settings.config_changed.connect(lambda _config: assistant.on_settings_changed())

    # -- Lo que lee la vista -----------------------------------

    @property
    def turns(self) -> list[ChatTurn]:
        return self.assistant.turns

    @property
    def model(self) -> str:
        return self.assistant.model

    @property
    def effort(self) -> str:
        return self.assistant.effort

    @property
    def config(self) -> ClaudeModelConfig:
        return self.assistant.config

    @property
    def sending(self) -> bool:
        return self.assistant.sending

    @property
    def last_first_text_s(self) -> float | None:
        return self.assistant.last_first_text_s

    # -- Pedidos de la vista -----------------------------------

    def set_model(self, model: str) -> None:
        self.assistant.set_model(model)

    def set_effort(self, effort: str) -> None:
        self.assistant.set_effort(effort)

    def send(self, text: str) -> bool:
        return self.assistant.send(text)

    def cancel(self) -> None:
        self.assistant.cancel()

    def clear(self) -> None:
        self.assistant.clear()

    def close(self) -> None:
        """Cancela el envío en curso y espera a su hilo; la ventana lo llama al cerrarse."""
        self.assistant.close()

    # -- Internos ----------------------------------------------

    @Slot(object)
    def _run_posted(self, task: Callable[[], None]) -> None:
        task()
