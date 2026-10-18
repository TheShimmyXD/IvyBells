"""
Coordinador del módulo Agente: une la máquina de estados, la selección, el prompt y el worker.

Lee el texto del interlocutor de la misma escucha en vivo (`LiveCoordinator`), así que
cambiar de módulo no detiene ni recarga nada. La vista solo habla con él.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, QThread, Signal, Slot

from coordinator_live import LiveCoordinator
from core.agent_prompt import Exchange, build_prompt
from core.agent_selection import Selection, WordPos, select_range, word_at
from core.agent_state import AgentLogic, AgentState
from core.claude_model import ClaudeModelConfig
from core.live_view import SOURCES
from services.service_claude import ClaudeCli, ClaudeService
from workers.worker_agent import AgentWorker
from workers.worker_runner import RequestSequence, start_worker, stop_thread

logger = logging.getLogger(__name__)

# (alias para la CLI, nombre en el botón, ayuda)
AGENT_MODELS = (
    ("haiku", "haiku", "El más barato; primer texto en ~2 s"),
    ("sonnet", "sonnet", "Equilibrado; primer texto en ~2 s"),
    ("opus", "opus", "El más capaz; primer texto en ~3 s"),
)
CLOSE_TIMEOUT_MS = 5_000

ServiceFactory = Callable[[ClaudeModelConfig], ClaudeService]


@dataclass(slots=True)
class AgentTurn:
    """Un envío: el rango marcado, a qué modelo y lo que va llegando de la respuesta."""

    source: str
    selection: Selection
    model: str
    answer: str = ""
    error: str = ""
    cancelled: bool = False
    done: bool = False


class AgentCoordinator(QObject):
    """
    Signals
    -------
    state_changed(dict) -> `state` y `status` de la máquina de estados.
    turns_changed()     -> cambió la lista de turnos o la respuesta en curso.
    marks_changed()     -> cambió el inicio marcado o los rangos enviados (resaltado).
    """

    state_changed = Signal(dict)
    turns_changed = Signal()
    marks_changed = Signal()

    def __init__(
        self,
        live: LiveCoordinator,
        config: ClaudeModelConfig | None = None,
        service_factory: ServiceFactory = ClaudeCli,
        save_config: Callable[[ClaudeModelConfig], object] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.live = live
        self.config = config or ClaudeModelConfig()
        self._service_factory = service_factory
        self._save_config = save_config
        self.logic = AgentLogic()
        self.speaker = SOURCES[0]
        self.turns: list[AgentTurn] = []
        self._history: list[Exchange] = []
        self._requests = RequestSequence()
        self._cancel = threading.Event()
        self._worker: AgentWorker | None = None
        self._thread: QThread | None = None
        live.session_started.connect(self.reset)

    # -- Pedidos de la vista -----------------------------------

    @property
    def start_mark(self) -> WordPos | None:
        return self.logic.start

    def sent_ranges(self, source: str) -> list[tuple[WordPos, WordPos]]:
        """Rangos ya enviados del interlocutor, para resaltarlos."""
        return [
            (turn.selection.start, turn.selection.end)
            for turn in self.turns
            if turn.source == source
        ]

    def set_speaker(self, source: str) -> None:
        if source == self.speaker or source not in SOURCES:
            return
        if self.logic.state is AgentState.START_MARKED:
            self.logic.cancel()
        self.speaker = source
        self.marks_changed.emit()
        self._emit_state()

    def set_model(self, model: str) -> None:
        if model == self.config.model:
            return
        self.config = replace(self.config, model=model)
        if self._save_config is not None:
            self._save_config(self.config)

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
        bounds = self.logic.mark_end(pos, self.config.model)
        if bounds is None:
            return
        selection = select_range(self.live.transcript.finals(self.speaker), *bounds)
        if selection is None:
            self.logic.cancel()
            self._emit_state()
            return
        self.turns.append(AgentTurn(self.speaker, selection, self.config.model))
        self._launch(build_prompt(self._history, selection.text()))
        self.marks_changed.emit()
        self.turns_changed.emit()
        self._emit_state()

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

    def close(self) -> None:
        """Cancela el envío en curso y espera al worker; la ventana lo llama al cerrarse."""
        self._cancel.set()
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker (llegan en el hilo principal) ------

    @Slot(str)
    def on_text(self, chunk: str) -> None:
        if self.turns and not self.turns[-1].done:
            self.turns[-1].answer += chunk
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
        if payload.get("cancelled"):
            turn.cancelled = True
        elif not turn.error:
            turn.answer = payload.get("answer") or turn.answer
            self._history.append(Exchange(turn.selection.text(), turn.answer))
            self.logic.answered()
        self.turns_changed.emit()
        self._emit_state()

    # -- Internos ----------------------------------------------

    def _position(self, phrase: int, offset: int) -> WordPos | None:
        finals = self.live.transcript.finals(self.speaker)
        if not 0 <= phrase < len(finals):
            return None
        return WordPos(phrase, word_at(finals[phrase].text, offset))

    def _launch(self, prompt: str) -> None:
        self._cancel = threading.Event()
        worker = self._worker = AgentWorker(
            service=self._service_factory(self.config),
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
