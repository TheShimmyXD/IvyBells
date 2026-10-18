"""Modo anticipado del coordinador del Agente, con un reloj falso."""

from __future__ import annotations

import threading
import time
from datetime import datetime

import pytest
from PySide6.QtCore import QObject, Signal

from core.agent_state import AgentState
from core.engine import TranscriptEvent
from core.live_view import LiveTranscript
from services.service_claude import ClaudeCancelled, Finished


class _FakeLive(QObject):
    session_started = Signal()
    sources_changed = Signal()
    transcript_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.closed_sources: set[str] = set()
        self.transcript = LiveTranscript()
        self.transcript.reset(datetime(2026, 10, 18, 18, 0, 0))
        self.say("ellos", "buenas tardes", 0.0)
        self.say("tu", "hola con gusto", 3.0)

    def say(self, source: str, text: str, start_s: float) -> None:
        self.transcript.apply(TranscriptEvent(source, True, text, start_s, start_s + 1.0))
        self.transcript_changed.emit(source)

    def speaking(self, source: str, text: str, start_s: float) -> None:
        self.transcript.apply(TranscriptEvent(source, False, text, start_s, start_s + 1.0))
        self.transcript_changed.emit(source)


class _Replies:
    """Una respuesta por envío (la última se repite), con pausa entre trozos."""

    def __init__(self, answers: list[list[str]], pause_s: float = 0.0) -> None:
        self.answers = answers
        self.pause_s = pause_s
        self.prompts: list[str] = []

    def ask(self, prompt: str, on_text, cancel: threading.Event) -> Finished:
        self.prompts.append(prompt)
        chunks = self.answers[min(len(self.prompts), len(self.answers)) - 1]
        for chunk in chunks:
            if cancel.wait(self.pause_s) if self.pause_s else cancel.is_set():
                raise ClaudeCancelled()
            on_text(chunk)
        return Finished("".join(chunks), False)


def _wait(qapp, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition():
        qapp.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("se agotó la espera")
        time.sleep(0.01)


@pytest.fixture
def ahead(qapp):
    from coordinator_agent import AHEAD, AgentCoordinator

    made = []

    def build(service):
        now = [100.0]
        live = _FakeLive()
        coordinator = AgentCoordinator(
            live, service_factory=lambda _config, _prompt: service, clock=lambda: now[0]
        )
        coordinator.set_mode(AHEAD)
        made.append(coordinator)
        return live, coordinator, now

    yield build
    for coordinator in made:
        coordinator.close()


def _idle(coordinator):
    return coordinator._thread is None and coordinator.logic.state is not AgentState.SENDING


def _turn_part(prompt: str) -> str:
    return prompt.split("Su último turno:")[1]


def test_waits_for_the_silence_then_sends_the_whole_conversation(qapp, ahead):
    service = _Replies([["4."]])
    live, coordinator, now = ahead(service)
    live.say("ellos", "¿cuánto es dos por dos?", 10.0)
    now[0] = 101.0
    coordinator._tick()
    assert service.prompts == []
    now[0] = 101.6
    coordinator._tick()
    _wait(qapp, lambda: _idle(coordinator))
    prompt = service.prompts[0]
    assert "buenas tardes" in prompt.split("Su último turno:")[0]
    assert "(otro participante) hola con gusto" in prompt
    assert "dos por dos" in _turn_part(prompt) and "buenas tardes" not in _turn_part(prompt)
    assert coordinator.turns[0].first_text_s == pytest.approx(1.6)


def test_dash_is_hidden_and_the_next_turn_sees_the_shown_answer(qapp, ahead):
    service = _Replies([["-"], ["4."], ["6."]])
    live, coordinator, now = ahead(service)
    for start_s, text in ((10.0, "hoy revisé los pedidos"), (20.0, "¿cuánto es dos por dos?")):
        live.say("ellos", text, start_s)
        now[0] += 10.0
        coordinator._tick()
        _wait(qapp, lambda: _idle(coordinator))
    assert not coordinator.turns[0].counts
    assert coordinator._history[0].answer == "4."
    live.say("ellos", "¿y lo anterior más dos?", 30.0)
    now[0] += 10.0
    coordinator._tick()
    _wait(qapp, lambda: _idle(coordinator))
    assert "(sugerencia) 4." in service.prompts[2]
    assert "dos por dos" in service.prompts[2]
    assert "pedidos" not in _turn_part(service.prompts[2])


def test_resuming_cancels_the_send_and_resends_the_whole_turn(qapp, ahead):
    service = _Replies([["a", "b", "c", "d"]], pause_s=0.3)
    live, coordinator, now = ahead(service)
    live.say("ellos", "quería saber el precio", 10.0)
    now[0] = 102.0
    coordinator._tick()
    assert coordinator.logic.state is AgentState.SENDING
    live.speaking("ellos", "y también", 14.0)
    _wait(qapp, lambda: _idle(coordinator))
    assert coordinator.turns[0].superseded and not coordinator.turns[0].counts
    live.say("ellos", "y también el plan anual", 14.0)
    now[0] = 104.0
    coordinator._tick()
    assert "quería saber" in _turn_part(service.prompts[1])
    assert "plan anual" in _turn_part(service.prompts[1])


def test_shown_answer_is_superseded_only_if_resumed_within_3_s(qapp, ahead):
    service = _Replies([["primera"], ["segunda"]])
    live, coordinator, now = ahead(service)
    live.say("ellos", "una cosa", 10.0)
    now[0] = 102.0
    coordinator._tick()
    _wait(qapp, lambda: _idle(coordinator))
    now[0] = 103.5
    live.speaking("ellos", "y otra", 12.0)
    assert coordinator.turns[0].superseded
    live.say("ellos", "y otra más", 12.0)
    now[0] = 106.0
    coordinator._tick()
    _wait(qapp, lambda: _idle(coordinator))
    assert "una cosa" in _turn_part(service.prompts[1])
    now[0] = 110.0
    live.speaking("ellos", "gracias", 20.0)
    assert not coordinator.turns[1].superseded
    assert [turn.answer for turn in coordinator._history] == ["segunda"]


def test_other_channel_speaking_closes_the_turn_without_waiting(qapp, ahead):
    service = _Replies([["claro"]])
    live, coordinator, now = ahead(service)
    live.say("ellos", "¿me ayuda?", 10.0)
    now[0] = 100.3
    live.speaking("tu", "sí", 11.0)
    _wait(qapp, lambda: _idle(coordinator))
    assert len(service.prompts) == 1


def test_status_says_who_is_listened_to(qapp, ahead):
    _live, coordinator, _now = ahead(_Replies([["x"]]))
    assert coordinator.status == "Anticipado: escuchando a Ellos"
