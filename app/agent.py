"""
Agente: une la máquina de estados, la selección, el prompt y el envío a Claude.

Lee el texto del interlocutor de la misma escucha en vivo (`LiveText`), así que cambiar
de módulo no detiene ni recarga nada; el modelo, el perfil y el contexto salen de
`ClaudeSetup`. También lleva cuánto de la ventana del modelo ocupa el envío (`budget`).

Dos modos: en el manual se envía lo que se marca con clics; en el anticipado se envía
toda la conversación cuando termina cada turno del interlocutor (`TurnWatcher`), y los
clics siguen como envío forzado. Como la escucha, todo cambia en el hilo dueño:
los envíos y el pulso del anticipado le llegan por `post`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.claude_ask import AskCallbacks, AskSlot, ClaudeSetup, LiveText, ServiceFactory, claude_cli
from app.live import Post, call_now
from domain.agent.agent_ahead import (
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
from domain.agent.agent_prompt import Exchange, build_ahead_prompt, build_prompt
from domain.agent.agent_selection import Selection, WordPos, select_phrases, word_at
from domain.agent.agent_state import AgentLogic, AgentState
from domain.agent.context_budget import MEASURED_WINDOWS, ContextBudget, build_budget
from domain.claude.claude_stream import Usage
from domain.transcription.live_view import SOURCES

logger = logging.getLogger(__name__)

CLOSE_TIMEOUT_S = 5.0
TICK_S = 0.2
SPEAKER_NAMES = {"ellos": "Ellos", "tu": "Tú"}


def _ignore(*_args: object) -> None:
    pass


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


@dataclass
class AgentListeners:
    """
    Avisos del Agente a su dueño, siempre en el hilo dueño. Por defecto no hacen nada.

    state(dict) -> `state` y `status` de la máquina de estados.
    turns()     -> cambió la lista de turnos o la respuesta en curso.
    marks()     -> cambió el inicio marcado o los rangos enviados (resaltado).
    budget()    -> cambió el presupuesto de contexto (`budget`).
    mode(str)   -> pasó a modo manual o anticipado.
    """

    state: Callable[[dict], None] = _ignore
    turns: Callable[[], None] = _ignore
    marks: Callable[[], None] = _ignore
    budget: Callable[[], None] = _ignore
    mode: Callable[[str], None] = _ignore


class AgentAssistant:
    """
    Caso de uso del Agente. Se usa desde un solo hilo (el dueño), que también le pasa los
    avisos de la escucha: `reset` (sesión nueva), `on_transcript` y `on_sources_changed`.
    """

    def __init__(
        self,
        live: LiveText,
        setup: ClaudeSetup,
        service_factory: ServiceFactory = claude_cli,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.live = live
        self.setup = setup
        self._service_factory = service_factory
        self.logic = AgentLogic()
        self.listeners = AgentListeners()
        self._post: Post = call_now
        self.speaker = self._open_sources()[0]
        self.turns: list[AgentTurn] = []
        self.mode = MANUAL
        self._clock = clock
        self._watcher = TurnWatcher()
        self._ahead_from = 0
        self._seen = {source: len(live.transcript.finals(source)) for source in SOURCES}
        self._ticks_stop = threading.Event()
        self._ticks_stop.set()
        self._ask = AskSlot()
        # La ventana de cada modelo; la del primer envío reemplaza a la medida en el banco.
        self._windows = dict(MEASURED_WINDOWS)
        self._budget: ContextBudget | None = None
        self.refresh_budget()

    def attach(self, post: Post, listeners: AgentListeners) -> None:
        """Fija el hilo dueño y quién recibe los avisos; la puerta lo llama una vez al armarse."""
        self._post = post
        self.listeners = listeners

    # -- Lo que lee la puerta ----------------------------------

    @property
    def busy(self) -> bool:
        """Hay un envío corriendo o cerrándose."""
        return self._ask.busy

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
    def history(self) -> list[Exchange]:
        return [
            Exchange(turn.selection.text(), shown_answer(turn.answer))
            for turn in self.turns
            if turn.counts
        ]

    def sent_ranges(self, source: str) -> list[tuple[WordPos, WordPos]]:
        """Rangos ya enviados del interlocutor, para resaltarlos."""
        return [
            (turn.selection.start, turn.selection.end)
            for turn in self.turns
            if turn.source == source
        ]

    # -- Pedidos de la puerta ----------------------------------

    def set_mode(self, mode: str) -> None:
        if mode == self.mode or mode not in AGENT_MODES:
            return
        self.mode = mode
        self._watch_from_now()
        if mode == AHEAD:
            self._start_ticks()
        else:
            self._ticks_stop.set()
        self.listeners.mode(mode)
        self._emit_state()
        self.listeners.turns()
        self.refresh_budget()

    def set_speaker(self, source: str) -> None:
        """Solo un canal abierto puede ser el interlocutor."""
        if source == self.speaker or source not in self._open_sources():
            return
        if self.logic.state is AgentState.START_MARKED:
            self.logic.cancel()
        self.speaker = source
        self._watch_from_now()
        self.listeners.marks()
        self._emit_state()

    def mark_start(self, phrase: int, offset: int) -> None:
        pos = self._position(phrase, offset)
        if pos is not None and self._sending_ahead():
            self.cancel()  # el clic manda: es un envío forzado
        if pos is not None and self.logic.mark_start(pos):
            self.listeners.marks()
            self._emit_state()

    def mark_end(self, phrase: int, offset: int) -> None:
        pos = self._position(phrase, offset)
        if pos is None:
            return
        if self.busy:
            # Un envío cancelado todavía se está cerrando: el inicio queda marcado.
            logger.warning("El envío anterior aún se está cerrando")
            return
        bounds = self.logic.mark_end(pos, self.setup.config.model)
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
                self.setup.config.model,
                clock=f"{datetime.now():%H:%M:%S}",
                sent_at=self._clock(),
            )
        )
        self._ahead_from = max(self._ahead_from, bounds[1].phrase + 1)
        self._watcher.taken()
        self._launch(build_prompt(self.history, selection.text()))
        self.listeners.marks()
        self.listeners.turns()
        self._emit_state()
        self.refresh_budget()

    def cancel(self) -> None:
        sending = self.logic.state is AgentState.SENDING
        if not self.logic.cancel():
            return
        if sending:
            self._ask.cancel()
        self.listeners.marks()
        self._emit_state()

    def reset(self) -> None:
        """Sesión nueva: las posiciones viejas ya no existen."""
        if self.busy:
            self._ask.cancel()
        self.logic.cancel()
        self.logic.reset()
        self.turns.clear()
        self._seen = dict.fromkeys(SOURCES, 0)
        self._watch_from_now()
        self.listeners.turns()
        self.listeners.marks()
        self._emit_state()
        self.refresh_budget()

    def close(self, timeout_s: float = CLOSE_TIMEOUT_S) -> None:
        """Cancela el envío en curso y espera a su hilo; la puerta lo llama al cerrarse."""
        self._ticks_stop.set()
        self._ask.close(timeout_s)

    def refresh_budget(self) -> None:
        """
        Rehace el presupuesto: el fragmento es el del envío en curso (si no, ninguno) y
        la cifra real, la del último envío que la trajo.
        """
        profiles = self.setup.profiles
        sending = self.turns[-1] if self.turns and not self.turns[-1].done else None
        measured = next((turn for turn in reversed(self.turns) if turn.usage), None)
        if self.mode == AHEAD:
            # Cada envío lleva la conversación entera: va toda como fragmento.
            finals = self.live.transcript.finals(self.speaker)
            history, fragment = [], build_ahead_prompt(self._said(), finals[self._ahead_from :])
        else:
            history, fragment = self.history, sending.selection.text() if sending else ""
        self._budget = build_budget(
            profiles.system_prompt(""),
            profiles.system_prompt(self.setup.context.text()),
            history,
            fragment,
            self._windows.get(self.setup.config.model),
            measured.usage if measured else None,
            measured.first_text_s if measured else None,
        )
        self.listeners.budget()

    # -- Avisos de la escucha y de la configuración ------------

    def on_context_reloaded(self, payload: dict) -> None:
        if payload.get("level") != "busy":
            self.refresh_budget()

    def on_sources_changed(self) -> None:
        """Si se cerró el canal del interlocutor, pasa al que quedó abierto."""
        if self.speaker not in self._open_sources():
            self.set_speaker(self._open_sources()[0])

    def on_transcript(self, source: str) -> None:
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
            self.tick()

    def tick(self) -> None:
        """Si venció el turno del interlocutor, envía toda la conversación."""
        if self.mode != AHEAD or self.busy:
            return
        if not self._watcher.due(self._clock()):
            return
        finals = self.live.transcript.finals(self.speaker)
        first = self._ahead_from
        if first >= len(finals):
            self._watcher.taken()
            return
        if not self.logic.begin(self.setup.config.model):
            return  # hay un inicio marcado: espera a que el autor termine
        self._watcher.taken()
        selection = select_phrases(finals, WordPos(first, 0), WordPos(len(finals) - 1, 0))
        self.turns.append(
            AgentTurn(
                self.speaker,
                selection,
                self.setup.config.model,
                clock=f"{datetime.now():%H:%M:%S}",
                sent_at=self._watcher.last_final,
                mode=AHEAD,
                turn_from=first,
            )
        )
        self._ahead_from = len(finals)
        self._launch(build_ahead_prompt(self._said(), list(selection.lines)))
        self.listeners.marks()
        self.listeners.turns()
        self._emit_state()
        self.refresh_budget()

    # -- Avisos del envío (ya en el hilo dueño) ----------------

    def on_text(self, chunk: str) -> None:
        if self.turns and not self.turns[-1].done:
            turn = self.turns[-1]
            if turn.first_text_s is None:
                turn.first_text_s = self._clock() - turn.sent_at
            turn.answer += chunk
            self.listeners.turns()

    def on_failed(self, message: str) -> None:
        if self.turns and not self.turns[-1].done:
            self.turns[-1].error = message
        self.logic.fail(message)
        self._emit_state()

    def on_finished(self, payload: dict) -> None:
        if not self.turns:
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
        self.listeners.turns()
        self._emit_state()
        self.refresh_budget()

    # -- Internos ----------------------------------------------

    def _start_ticks(self) -> None:
        """Pulso del anticipado: cada `TICK_S` pide `tick()` en el hilo dueño."""
        self._ticks_stop.set()
        stop = self._ticks_stop = threading.Event()
        post = self._post

        def beat() -> None:
            while not stop.wait(TICK_S):
                post(self.tick)

        threading.Thread(target=beat, name="ivybells-ahead", daemon=True).start()

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
        self.listeners.turns()
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

    def _position(self, phrase: int, offset: int) -> WordPos | None:
        finals = self.live.transcript.finals(self.speaker)
        if not 0 <= phrase < len(finals):
            return None
        # La vista muestra las palabras separadas por un espacio: la posición es sobre eso.
        return WordPos(phrase, word_at(" ".join(finals[phrase].text.split()), offset))

    def _launch(self, prompt: str) -> None:
        setup = self.setup
        service = self._service_factory(
            setup.config, setup.profiles.system_prompt(setup.context.text())
        )
        self._ask.launch(
            service,
            prompt,
            self._post,
            AskCallbacks(text=self.on_text, failed=self.on_failed, finished=self.on_finished),
        )

    def _emit_state(self) -> None:
        self.listeners.state({"state": self.logic.state, "status": self.status})
