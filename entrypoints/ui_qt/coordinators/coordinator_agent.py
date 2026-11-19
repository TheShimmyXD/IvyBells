"""
Adaptador Qt del Agente (`app.agent.AgentAssistant`).

La vista solo habla con él. La orquestación vive en `app/`; aquí se pasan los avisos de los
hilos del Agente (envíos y pulso del anticipado) al hilo de la ventana, se convierten en
señales y se le llevan al Agente las señales de la escucha y de Configuración.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from app.agent import AHEAD, MANUAL, AgentAssistant, AgentListeners, AgentTurn
from app.claude_ask import ServiceFactory, claude_cli
from domain.agent.agent_prompt import Exchange
from domain.agent.agent_selection import WordPos
from domain.agent.agent_state import AgentLogic
from domain.agent.context_budget import ContextBudget
from entrypoints.ui_qt.coordinators.coordinator_config import ClaudeSettings
from entrypoints.ui_qt.coordinators.coordinator_live import LiveCoordinator

__all__ = ["AHEAD", "MANUAL", "AgentCoordinator", "AgentTurn"]


class AgentCoordinator(QObject):
    """
    Signals
    -------
    state_changed(dict) -> `state` y `status` de la máquina de estados.
    turns_changed()     -> cambió la lista de turnos o la respuesta en curso.
    marks_changed()     -> cambió el inicio marcado o los rangos enviados (resaltado).
    budget_changed()    -> cambió el presupuesto de contexto (`budget`).
    mode_changed(str)   -> pasó a modo manual o anticipado.
    """

    state_changed = Signal(dict)
    turns_changed = Signal()
    marks_changed = Signal()
    budget_changed = Signal()
    mode_changed = Signal(str)
    # Tarea que llega de un hilo del Agente: Qt la pone en cola y la corre en este hilo.
    _posted = Signal(object)

    # Las capturas lo cambian por uno que no lanza la CLI.
    assistant_class: type[AgentAssistant] = AgentAssistant

    def __init__(
        self,
        live: LiveCoordinator,
        settings: ClaudeSettings | None = None,
        service_factory: ServiceFactory = claude_cli,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.live = live
        self.settings = settings or ClaudeSettings(parent=self)
        assistant = self.assistant = self.assistant_class(
            live, self.settings, service_factory, clock
        )
        self._posted.connect(self._run_posted)
        assistant.attach(
            self._posted.emit,
            AgentListeners(
                state=self.state_changed.emit,
                turns=self.turns_changed.emit,
                marks=self.marks_changed.emit,
                budget=self.budget_changed.emit,
                mode=self.mode_changed.emit,
            ),
        )
        live.session_started.connect(assistant.reset)
        live.sources_changed.connect(assistant.on_sources_changed)
        live.transcript_changed.connect(assistant.on_transcript)
        settings = self.settings
        settings.config_changed.connect(lambda _config: assistant.refresh_budget())
        settings.profiles.active_changed.connect(lambda _name: assistant.refresh_budget())
        settings.profiles.profiles_changed.connect(assistant.refresh_budget)
        settings.context.reloaded.connect(assistant.on_context_reloaded)

    # -- Lo que lee la vista -----------------------------------

    @property
    def logic(self) -> AgentLogic:
        return self.assistant.logic

    @property
    def turns(self) -> list[AgentTurn]:
        return self.assistant.turns

    @property
    def mode(self) -> str:
        return self.assistant.mode

    @property
    def speaker(self) -> str:
        return self.assistant.speaker

    @property
    def busy(self) -> bool:
        return self.assistant.busy

    @property
    def start_mark(self) -> WordPos | None:
        return self.assistant.start_mark

    @property
    def last_first_text_s(self) -> float | None:
        return self.assistant.last_first_text_s

    @property
    def budget(self) -> ContextBudget:
        return self.assistant.budget

    @property
    def status(self) -> str:
        return self.assistant.status

    @property
    def history(self) -> list[Exchange]:
        return self.assistant.history

    def sent_ranges(self, source: str) -> list[tuple[WordPos, WordPos]]:
        return self.assistant.sent_ranges(source)

    # -- Pedidos de la vista -----------------------------------

    def set_mode(self, mode: str) -> None:
        self.assistant.set_mode(mode)

    def set_speaker(self, source: str) -> None:
        self.assistant.set_speaker(source)

    def mark_start(self, phrase: int, offset: int) -> None:
        self.assistant.mark_start(phrase, offset)

    def mark_end(self, phrase: int, offset: int) -> None:
        self.assistant.mark_end(phrase, offset)

    def cancel(self) -> None:
        self.assistant.cancel()

    def reset(self) -> None:
        self.assistant.reset()

    def close(self) -> None:
        """Cancela el envío en curso y espera a su hilo; la ventana lo llama al cerrarse."""
        self.assistant.close()

    # -- Internos ----------------------------------------------

    @Slot(object)
    def _run_posted(self, task: Callable[[], None]) -> None:
        task()
