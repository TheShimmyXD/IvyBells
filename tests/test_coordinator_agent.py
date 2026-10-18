from __future__ import annotations

import threading
import time
from datetime import datetime

import pytest
from PySide6.QtCore import QObject, Signal

from core.agent_state import AgentState
from core.engine import TranscriptEvent
from core.live_view import LiveTranscript
from services.service_claude import ScriptedClaude
from workers.worker_agent import AgentWorker


class _FakeLive(QObject):
    """Lo que el coordinador del Agente usa de la escucha en vivo."""

    session_started = Signal()
    sources_changed = Signal()

    def __init__(self, phrases: dict[str, list[str]]) -> None:
        super().__init__()
        self.closed_sources: set[str] = set()
        self.transcript = LiveTranscript()
        self.transcript.reset(datetime(2026, 10, 17, 10, 0, 0))
        for source, texts in phrases.items():
            for index, text in enumerate(texts):
                self.transcript.apply(TranscriptEvent(source, True, text, index * 4.0, 1.0))


PHRASES = {
    "ellos": ["buenas tardes", "quería saber el precio del plan"],
    "tu": ["hola con gusto"],
}


def _wait(qapp, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition():
        qapp.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("se agotó la espera")
        time.sleep(0.01)


@pytest.fixture
def make(qapp):
    from coordinator_agent import AgentCoordinator

    made = []

    def build(service):
        live = _FakeLive(PHRASES)
        coordinator = AgentCoordinator(live, service_factory=lambda _config, _prompt: service)
        made.append(coordinator)
        return live, coordinator

    yield build
    for coordinator in made:
        coordinator.close()
        _wait(qapp, lambda c=coordinator: c._thread is None)


def test_range_is_sent_and_answer_streams_in(qapp, make):
    service = ScriptedClaude(["Con gusto, ", "el plan cuesta..."])
    _live, coordinator = make(service)
    states = []
    coordinator.state_changed.connect(lambda payload: states.append(payload["state"]))
    coordinator.mark_start(1, 7)  # "saber"
    coordinator.mark_end(0, 0)  # "buenas": queda antes y se invierte
    _wait(qapp, lambda: coordinator.logic.state is AgentState.ANSWERED)
    turn = coordinator.turns[0]
    assert turn.selection.text() == ("[10:00:00] buenas tardes\n[10:00:04] quería saber")
    assert turn.answer == "Con gusto, el plan cuesta..."
    assert "<cliente>\n[10:00:00] buenas tardes" in service.prompts[0]
    assert states[:2] == [AgentState.START_MARKED, AgentState.SENDING]


def test_second_turn_carries_the_history(qapp, make):
    service = ScriptedClaude(["respuesta uno"])
    _live, coordinator = make(service)
    coordinator.mark_start(0, 0)
    coordinator.mark_end(0, 99)
    _wait(qapp, lambda: coordinator._thread is None)
    coordinator.mark_start(1, 0)
    coordinator.mark_end(1, 99)
    _wait(qapp, lambda: len(service.prompts) == 2 and coordinator._thread is None)
    assert "<respuesta>\nrespuesta uno\n</respuesta>" in service.prompts[1]
    assert coordinator.sent_ranges("ellos")[1][0].phrase == 1


def test_speaker_change_reads_the_other_source(qapp, make):
    service = ScriptedClaude(["ok"])
    _live, coordinator = make(service)
    coordinator.mark_start(0, 0)
    coordinator.set_speaker("tu")
    assert coordinator.logic.state is AgentState.IDLE
    coordinator.mark_start(0, 0)
    coordinator.mark_end(0, 99)
    _wait(qapp, lambda: coordinator._thread is None)
    assert coordinator.turns[0].selection.text() == "[10:00:00] hola con gusto"


def test_closed_channel_is_not_offered_as_speaker(qapp, make):
    live, coordinator = make(ScriptedClaude(["ok"]))
    coordinator.mark_start(0, 0)
    live.closed_sources.add("ellos")
    live.sources_changed.emit()
    assert coordinator.speaker == "tu"
    assert coordinator.logic.state is AgentState.IDLE
    coordinator.set_speaker("ellos")
    assert coordinator.speaker == "tu"
    live.closed_sources.clear()
    live.sources_changed.emit()
    coordinator.set_speaker("ellos")
    assert coordinator.speaker == "ellos"


def test_failure_marks_the_turn_and_the_state(qapp, make):
    _live, coordinator = make(ScriptedClaude(["a medias"], error="Límite de uso alcanzado"))
    coordinator.mark_start(0, 0)
    coordinator.mark_end(0, 5)
    _wait(qapp, lambda: coordinator._thread is None)
    assert coordinator.logic.state is AgentState.ERROR
    assert coordinator.turns[0].error == "Límite de uso alcanzado"
    assert coordinator._history == []


def test_cancel_while_sending(qapp, make):
    _live, coordinator = make(ScriptedClaude(["uno ", "dos ", "tres"], pause_s=0.3))
    coordinator.mark_start(0, 0)
    coordinator.mark_end(0, 5)
    coordinator.cancel()
    _wait(qapp, lambda: coordinator._thread is None)
    assert coordinator.turns[0].cancelled
    assert coordinator.logic.state is AgentState.IDLE
    assert coordinator._history == []


def test_new_session_forgets_turns(qapp, make):
    live, coordinator = make(ScriptedClaude(["ok"]))
    coordinator.mark_start(0, 0)
    coordinator.mark_end(0, 5)
    _wait(qapp, lambda: coordinator._thread is None)
    live.session_started.emit()
    assert coordinator.turns == []
    assert coordinator.logic.state is AgentState.IDLE


def test_click_outside_the_phrases_does_nothing(qapp, make):
    _live, coordinator = make(ScriptedClaude(["ok"]))
    coordinator.mark_start(9, 0)
    assert coordinator.logic.state is AgentState.IDLE


def test_worker_reports_cancel_and_answer(qapp):
    cancel = threading.Event()
    worker = AgentWorker(
        service=ScriptedClaude(["a", "b"]), prompt="p", cancel_event=cancel, request_id=3
    )
    got = {"text": [], "failed": [], "finished": []}
    for name, items in got.items():
        getattr(worker, name).connect(lambda *args, items=items: items.append(args))
    worker.run()
    assert [args[0] for args in got["text"]] == ["a", "b"]
    assert got["finished"][0][0] == {"_request_id": 3, "answer": "ab", "cancelled": False}


def test_active_profile_reaches_the_service(qapp, tmp_path):
    from coordinator_agent import AgentCoordinator
    from coordinator_config import ClaudeSettings
    from coordinator_context import AgentContext
    from coordinator_profiles import AgentProfiles
    from services.service_profiles import ProfileStore

    folder = tmp_path / "perfiles"
    folder.mkdir()
    (folder / "acme.md").write_text("Somos Acme.", encoding="utf-8")
    photo = tmp_path / "contexto.md"
    photo.write_text("Horario de 8 a 18.", encoding="utf-8")
    settings = ClaudeSettings(
        profiles=AgentProfiles(ProfileStore(folder), "acme"),
        context=AgentContext(target=photo),
    )
    system_prompts = []
    service = ScriptedClaude(["listo"])

    def factory(_config, system_prompt):
        system_prompts.append(system_prompt)
        return service

    coordinator = AgentCoordinator(_FakeLive(PHRASES), settings, service_factory=factory)
    coordinator.mark_start(0, 0)
    coordinator.mark_end(0, 0)
    _wait(qapp, lambda: coordinator.logic.state is AgentState.ANSWERED)
    coordinator.close()
    _wait(qapp, lambda: coordinator._thread is None)
    assert "Somos Acme." in system_prompts[0]
    assert system_prompts[0].startswith("Reglas de IvyBells")
    assert system_prompts[0].index("Somos Acme.") < system_prompts[0].index("Horario de 8 a 18.")
