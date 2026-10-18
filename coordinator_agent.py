"""
Coordinador del módulo Agente: une la máquina de estados, la selección, el prompt y el worker.

Lee el texto del interlocutor de la misma escucha en vivo (`LiveCoordinator`), así que
cambiar de módulo no detiene ni recarga nada; el modelo, el esfuerzo y la cuenta salen de
`ClaudeSettings` (módulo Configuración). La vista solo habla con él. También lleva cuánto
de la ventana del modelo ocupa el envío (`budget`), que muestran el Agente y Configuración.

Dos modos: en el manual se envía lo que se marca con clics; en el anticipado se
envía toda la conversación cuando termina cada turno del interlocutor (`TurnWatcher`), y
los clics siguen como envío forzado.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from coordinator_config import ClaudeSettings
from coordinator_live import LiveCoordinator
from core.agent_ahead import (
    AGENT_MODES,
    AHEAD,
    MANUAL,
    Said,
    TurnEvent,
    TurnWatcher,
    conversation,
    shown_answer,
    supersedes,
)
from core.agent_prompt import Exchange, build_ahead_prompt, build_prompt
from core.agent_selection import Selection, WordPos, select_phrases, word_at
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
TICK_MS = 200
SPEAKER_NAMES = {"ellos": "Ellos", "tu": "Tú"}

# Recibe el modelo y el system prompt (reglas, perfil activo y contexto).
ServiceFactory = Callable[[ClaudeModelConfig, str], ClaudeService]


@dataclass(slots=True)
class AgentTurn:
    """Un envío: el rango marcado (o el turno, en anticipado) y lo que llega de la respuesta."""

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
    mode: str = MANUAL
    turn_from: int = 0  # primera frase del turno (anticipado)
    done_at: float = 0.0
    done_clock: str = ""
    superseded: bool = False  # el interlocutor retomó: no entra al historial

    @property
    def counts(self) -> bool:
        """Si entra al historial: terminada, mostrada y sin cancelar, error ni superar."""
        return (
            self.done
            and not (self.cancelled or self.error or self.superseded)
            and bool(shown_answer(self.answer))
        )


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

    def __init__(
        self,
        live: LiveCoordinator,
        settings: ClaudeSettings | None = None,
        service_factory: ServiceFactory = ClaudeCli,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.live = live
        self.settings = settings or ClaudeSettings(parent=self)
        self._service_factory = service_factory
        self.logic = AgentLogic()
        self.speaker = self._open_sources()[0]
        self.turns: list[AgentTurn] = []
        self.mode = MANUAL
        self._clock = clock
        self._watcher = TurnWatcher()
        self._ahead_from = 0
        self._seen = {source: len(live.transcript.finals(source)) for source in SOURCES}
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._requests = RequestSequence()
        self._cancel = threading.Event()
        self._worker: AgentWorker | None = None
        self._thread: QThread | None = None
        # La ventana de cada modelo; la del primer envío reemplaza a la medida en el banco.
        self._windows = dict(MEASURED_WINDOWS)
        self._budget: ContextBudget | None = None
        live.session_started.connect(self.reset)
        live.sources_changed.connect(self._on_sources_changed)
        live.transcript_changed.connect(self._on_transcript)
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

    @property
    def status(self) -> str:
        if self.mode == AHEAD and self.logic.state in (AgentState.IDLE, AgentState.ANSWERED):
            return f"Anticipado: escuchando a {SPEAKER_NAMES.get(self.speaker, self.speaker)}"
        return self.logic.status

    @property
    def _history(self) -> list[Exchange]:
        return [
            Exchange(turn.selection.text(), shown_answer(turn.answer))
            for turn in self.turns
            if turn.counts
        ]

    def set_mode(self, mode: str) -> None:
        if mode == self.mode or mode not in AGENT_MODES:
            return
        self.mode = mode
        self._watch_from_now()
        if mode == AHEAD:
            self._timer.start()
        else:
            self._timer.stop()
        self.mode_changed.emit(mode)
        self._emit_state()
        self.turns_changed.emit()
        self.refresh_budget()

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
        self._watch_from_now()
        self.marks_changed.emit()
        self._emit_state()

    def mark_start(self, phrase: int, offset: int) -> None:
        pos = self._position(phrase, offset)
        if pos is not None and self._sending_ahead():
            self.cancel()  # el clic manda: es un envío forzado
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
        selection = select_phrases(self.live.transcript.finals(self.speaker), *bounds)
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
                sent_at=self._clock(),
            )
        )
        self._ahead_from = max(self._ahead_from, bounds[1].phrase + 1)
        self._watcher.taken()
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
        self._seen = dict.fromkeys(SOURCES, 0)
        self._watch_from_now()
        self.turns_changed.emit()
        self.marks_changed.emit()
        self._emit_state()
        self.refresh_budget()

    def close(self) -> None:
        """Cancela el envío en curso y espera al worker; la ventana lo llama al cerrarse."""
        self._timer.stop()
        self._cancel.set()
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker (llegan en el hilo principal) ------

    @Slot(str)
    def on_text(self, chunk: str) -> None:
        if self.turns and not self.turns[-1].done:
            turn = self.turns[-1]
            if turn.first_text_s is None:
                turn.first_text_s = self._clock() - turn.sent_at
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
        turn.done_at = self._clock()
        turn.done_clock = f"{datetime.now():%H:%M:%S}"
        turn.usage = payload.get("usage")
        if turn.usage is not None and turn.usage.context_window:
            self._windows[turn.model] = turn.usage.context_window
        if payload.get("cancelled"):
            turn.cancelled = True
        elif not turn.error:
            turn.answer = payload.get("answer") or turn.answer
            self.logic.answered()
            if turn.mode == AHEAD and turn.first_text_s is not None:
                logger.info(
                    "Anticipado: fin de frase a primer texto %.2f s, total %.2f s%s",
                    turn.first_text_s,
                    turn.done_at - turn.sent_at,
                    "" if shown_answer(turn.answer) else " (sin respuesta)",
                )
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
        if self.mode == AHEAD:
            # Cada envío lleva la conversación entera: va toda como fragmento.
            finals = self.live.transcript.finals(self.speaker)
            history, fragment = [], build_ahead_prompt(self._said(), finals[self._ahead_from :])
        else:
            history, fragment = self._history, sending.selection.text() if sending else ""
        self._budget = build_budget(
            profiles.system_prompt(""),
            profiles.system_prompt(self.settings.context.text()),
            history,
            fragment,
            self._windows.get(self.settings.config.model),
            measured.usage if measured else None,
            measured.first_text_s if measured else None,
        )
        self.budget_changed.emit()

    # -- Internos ----------------------------------------------

    def _on_context_reloaded(self, payload: dict) -> None:
        if payload.get("level") != "busy":
            self.refresh_budget()

    def _watch_from_now(self) -> None:
        """El anticipado responde desde aquí: lo ya dicho no se contesta."""
        self._watcher.reset()
        self._ahead_from = len(self.live.transcript.finals(self.speaker))

    def _sending_ahead(self) -> bool:
        return (
            self.logic.state is AgentState.SENDING
            and bool(self.turns)
            and self.turns[-1].mode == AHEAD
        )

    def _on_transcript(self, source: str) -> None:
        transcript = self.live.transcript
        count = len(transcript.finals(source))
        new_final = count > self._seen.get(source, 0)
        self._seen[source] = count
        if self.mode != AHEAD or source in self.live.closed_sources:
            return
        has_partial = transcript.partial(source) is not None
        event = self._watcher.update(source == self.speaker, new_final, has_partial, self._clock())
        if event is TurnEvent.RESUMED:
            self._supersede_last()
        elif event is TurnEvent.CLOSED:
            self._tick()

    def _supersede_last(self) -> None:
        """El interlocutor retomó: lo último enviado no respondía al turno completo."""
        turn = self.turns[-1] if self.turns else None
        if turn is None or turn.mode != AHEAD or turn.superseded or turn.source != self.speaker:
            return
        if not turn.done:
            turn.superseded = True
            self.cancel()
        elif turn.counts and supersedes(turn.done_at, self._clock()):
            turn.superseded = True
        else:
            return
        self._ahead_from = min(self._ahead_from, turn.turn_from)
        self._watcher.reopen()
        self.turns_changed.emit()
        self.refresh_budget()

    @Slot()
    def _tick(self) -> None:
        """Si venció el turno del interlocutor, envía toda la conversación."""
        if self.mode != AHEAD or self._thread is not None:
            return
        if not self._watcher.due(self._clock()):
            return
        finals = self.live.transcript.finals(self.speaker)
        first = self._ahead_from
        if first >= len(finals):
            self._watcher.taken()
            return
        if not self.logic.begin(self.settings.config.model):
            return  # hay un inicio marcado: espera a que el autor termine
        self._watcher.taken()
        selection = select_phrases(finals, WordPos(first, 0), WordPos(len(finals) - 1, 0))
        self.turns.append(
            AgentTurn(
                self.speaker,
                selection,
                self.settings.config.model,
                clock=f"{datetime.now():%H:%M:%S}",
                sent_at=self._watcher.last_final,
                mode=AHEAD,
                turn_from=first,
            )
        )
        self._ahead_from = len(finals)
        self._launch(build_ahead_prompt(self._said(), list(selection.lines)))
        self.marks_changed.emit()
        self.turns_changed.emit()
        self._emit_state()
        self.refresh_budget()

    def _said(self) -> list[Said]:
        finals = self.live.transcript.finals
        others = [source for source in self._open_sources() if source != self.speaker]
        suggestions = [
            (turn.done_clock, shown_answer(turn.answer)) for turn in self.turns if turn.counts
        ]
        return conversation(finals(self.speaker), finals(others[0]) if others else [], suggestions)

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
        self.state_changed.emit({"state": self.logic.state, "status": self.status})
