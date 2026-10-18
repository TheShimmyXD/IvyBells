"""
Coordinador del módulo Agente: une la máquina de estados, la selección, el prompt y el worker.

Lee el texto del interlocutor de la misma escucha en vivo (`LiveCoordinator`), así que
cambiar de módulo no detiene ni recarga nada; el modelo, el esfuerzo y la cuenta salen de
`ClaudeSettings` (módulo Configuración). La vista solo habla con él. También lleva cuánto
de la ventana del modelo ocupa el envío (`budget`), que muestran el Agente y Configuración.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal, Slot

from coordinator_config import ClaudeSettings
from coordinator_live import LiveCoordinator
from core.agent_prompt import Exchange, build_prompt
from core.agent_selection import Selection, WordPos, select_range, word_at
from core.agent_state import AgentLogic, AgentState
from core.claude_model import ClaudeModelConfig
from core.claude_stream import Usage
from core.context_budget import MEASURED_WINDOWS, ContextBudget, build_budget
from core.live_view import SOURCES
from services.service_claude import ClaudeCli, ClaudeService
from workers.worker_agent import AgentWorker
from workers.worker_runner import RequestSequence, start_worker, stop_thread

logger = logging.getLogger(__name__)

CLOSE_TIMEOUT_MS = 5_000

# Recibe el modelo y el system prompt (reglas, perfil activo y contexto).
ServiceFactory = Callable[[ClaudeModelConfig, str], ClaudeService]


@dataclass(slots=True)
class AgentTurn:
    """Un envío: el rango marcado, a qué modelo y lo que va llegando de la respuesta."""

    source: str
    selection: Selection
    model: str
    clock: str = ""
    sent_at: float = 0.0
    first_text_s: float | None = None
    answer: str = ""
    error: str = ""
    cancelled: bool = False
    done: bool = False
    usage: Usage | None = None


class AgentCoordinator(QObject):
    """
    Signals
    -------
    state_changed(dict) -> `state` y `status` de la máquina de estados.
    turns_changed()     -> cambió la lista de turnos o la respuesta en curso.
    marks_changed()     -> cambió el inicio marcado o los rangos enviados (resaltado).
    budget_changed()    -> cambió el presupuesto de contexto (`budget`).
    """

    state_changed = Signal(dict)
    turns_changed = Signal()
    marks_changed = Signal()
    budget_changed = Signal()

    def __init__(
        self,
        live: LiveCoordinator,
        settings: ClaudeSettings | None = None,
        service_factory: ServiceFactory = ClaudeCli,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.live = live
        self.settings = settings or ClaudeSettings(parent=self)
        self._service_factory = service_factory
        self.logic = AgentLogic()
        self.speaker = self._open_sources()[0]
        self.turns: list[AgentTurn] = []
        self._history: list[Exchange] = []
        self._requests = RequestSequence()
        self._cancel = threading.Event()
        self._worker: AgentWorker | None = None
        self._thread: QThread | None = None
        # La ventana de cada modelo; la del primer envío reemplaza a la medida en el banco.
        self._windows = dict(MEASURED_WINDOWS)
        self._budget: ContextBudget | None = None
        live.session_started.connect(self.reset)
        live.sources_changed.connect(self._on_sources_changed)
        settings = self.settings
        settings.config_changed.connect(lambda _config: self.refresh_budget())
        settings.profiles.active_changed.connect(lambda _name: self.refresh_budget())
        settings.profiles.profiles_changed.connect(self.refresh_budget)
        settings.context.reloaded.connect(self._on_context_reloaded)
        self.refresh_budget()

    # -- Pedidos de la vista -----------------------------------

    @property
    def start_mark(self) -> WordPos | None:
        return self.logic.start

    @property
    def last_first_text_s(self) -> float | None:
        """Segundos al primer texto del último turno que ya recibió algo."""
        for turn in reversed(self.turns):
            if turn.first_text_s is not None:
                return turn.first_text_s
        return None

    @property
    def budget(self) -> ContextBudget:
        return self._budget

    def sent_ranges(self, source: str) -> list[tuple[WordPos, WordPos]]:
        """Rangos ya enviados del interlocutor, para resaltarlos."""
        return [
            (turn.selection.start, turn.selection.end)
            for turn in self.turns
            if turn.source == source
        ]

    def set_speaker(self, source: str) -> None:
        """Solo un canal abierto puede ser el interlocutor."""
        if source == self.speaker or source not in self._open_sources():
            return
        if self.logic.state is AgentState.START_MARKED:
            self.logic.cancel()
        self.speaker = source
        self.marks_changed.emit()
        self._emit_state()

    def mark_start(self, phrase: int, offset: int) -> None:
        pos = self._position(phrase, offset)
        if pos is not None and self.logic.mark_start(pos):
            self.marks_changed.emit()
            self._emit_state()

    def mark_end(self, phrase: int, offset: int) -> None:
        pos = self._position(phrase, offset)
        if pos is None:
            return
        if self._thread is not None:
            # Un envío cancelado todavía se está cerrando: el inicio queda marcado.
            logger.warning("El envío anterior aún se está cerrando")
            return
        bounds = self.logic.mark_end(pos, self.settings.config.model)
        if bounds is None:
            return
        selection = select_range(self.live.transcript.finals(self.speaker), *bounds)
        if selection is None:
            self.logic.cancel()
            self._emit_state()
            return
        self.turns.append(
            AgentTurn(
                self.speaker,
                selection,
                self.settings.config.model,
                clock=f"{datetime.now():%H:%M:%S}",
                sent_at=time.monotonic(),
            )
        )
        self._launch(build_prompt(self._history, selection.text()))
        self.marks_changed.emit()
        self.turns_changed.emit()
        self._emit_state()
        self.refresh_budget()

    def cancel(self) -> None:
        sending = self.logic.state is AgentState.SENDING
        if not self.logic.cancel():
            return
        if sending:
            self._cancel.set()
        self.marks_changed.emit()
        self._emit_state()

    @Slot()
    def reset(self) -> None:
        """Sesión nueva: las posiciones viejas ya no existen."""
        if self._thread is not None:
            self._cancel.set()
        self.logic.cancel()
        self.logic.reset()
        self.turns.clear()
        self._history.clear()
        self.turns_changed.emit()
        self.marks_changed.emit()
        self._emit_state()
        self.refresh_budget()

    def close(self) -> None:
        """Cancela el envío en curso y espera al worker; la ventana lo llama al cerrarse."""
        self._cancel.set()
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker (llegan en el hilo principal) ------

    @Slot(str)
    def on_text(self, chunk: str) -> None:
        if self.turns and not self.turns[-1].done:
            turn = self.turns[-1]
            if turn.first_text_s is None:
                turn.first_text_s = time.monotonic() - turn.sent_at
            turn.answer += chunk
            self.turns_changed.emit()

    @Slot(str)
    def on_failed(self, message: str) -> None:
        if self.turns and not self.turns[-1].done:
            self.turns[-1].error = message
        self.logic.fail(message)
        self._emit_state()

    @Slot(dict)
    def on_finished(self, payload: dict) -> None:
        if not self._requests.is_current(payload) or not self.turns:
            return
        turn = self.turns[-1]
        turn.done = True
        turn.usage = payload.get("usage")
        if turn.usage is not None and turn.usage.context_window:
            self._windows[turn.model] = turn.usage.context_window
        if payload.get("cancelled"):
            turn.cancelled = True
        elif not turn.error:
            turn.answer = payload.get("answer") or turn.answer
            self._history.append(Exchange(turn.selection.text(), turn.answer))
            self.logic.answered()
        self.turns_changed.emit()
        self._emit_state()
        self.refresh_budget()

    @Slot()
    def refresh_budget(self) -> None:
        """
        Rehace el presupuesto: el fragmento es el del envío en curso (si no, ninguno) y
        la cifra real, la del último envío que la trajo.
        """
        profiles = self.settings.profiles
        sending = self.turns[-1] if self.turns and not self.turns[-1].done else None
        measured = next((turn for turn in reversed(self.turns) if turn.usage), None)
        self._budget = build_budget(
            profiles.system_prompt(""),
            profiles.system_prompt(self.settings.context.text()),
            self._history,
            sending.selection.text() if sending else "",
            self._windows.get(self.settings.config.model),
            measured.usage if measured else None,
            measured.first_text_s if measured else None,
        )
        self.budget_changed.emit()

    # -- Internos ----------------------------------------------

    def _on_context_reloaded(self, payload: dict) -> None:
        if payload.get("level") != "busy":
            self.refresh_budget()

    def _open_sources(self) -> list[str]:
        return [source for source in SOURCES if source not in self.live.closed_sources]

    def _on_sources_changed(self) -> None:
        """Si se cerró el canal del interlocutor, pasa al que quedó abierto."""
        if self.speaker not in self._open_sources():
            self.set_speaker(self._open_sources()[0])

    def _position(self, phrase: int, offset: int) -> WordPos | None:
        finals = self.live.transcript.finals(self.speaker)
        if not 0 <= phrase < len(finals):
            return None
        # La vista muestra las palabras separadas por un espacio: la posición es sobre eso.
        return WordPos(phrase, word_at(" ".join(finals[phrase].text.split()), offset))

    def _launch(self, prompt: str) -> None:
        self._cancel = threading.Event()
        worker = self._worker = AgentWorker(
            service=self._service_factory(
                self.settings.config,
                self.settings.profiles.system_prompt(self.settings.context.text()),
            ),
            prompt=prompt,
            cancel_event=self._cancel,
            request_id=self._requests.next(),
        )
        worker.text.connect(self.on_text)
        worker.failed.connect(self.on_failed)
        self._thread = start_worker(
            self, worker, on_done=self.on_finished, on_cleared=self._clear_refs
        )

    def _clear_refs(self) -> None:
        self._worker = None
        self._thread = None

    def _emit_state(self) -> None:
        self.state_changed.emit({"state": self.logic.state, "status": self.logic.status})
