"""El Agente y el chat sin Qt: los avisos llegan al hilo dueño por `post`."""

from __future__ import annotations

import contextlib
import queue
import threading
import time
from datetime import datetime

from app.agent import AHEAD, MANUAL, AgentAssistant, AgentListeners
from app.chat import ChatAssistant, ChatListeners
from domain.agent.agent_state import AgentState
from domain.claude.claude_model import ClaudeModelConfig
from domain.transcription.engine import TranscriptEvent
from domain.transcription.live_view import LiveTranscript
from services.service_claude import ScriptedClaude


class _Live:
    """Lo que el Agente y el chat leen de la escucha, sin Qt."""

    def __init__(self) -> None:
        self.closed_sources: set[str] = set()
        self.transcript = LiveTranscript()
        self.transcript.reset(datetime(2026, 11, 19, 9, 0, 0))
        self.say("ellos", "buenas tardes", 0.0)
        self.say("tu", "hola con gusto", 3.0)

    def say(self, source: str, text: str, start_s: float) -> None:
        self.transcript.apply(TranscriptEvent(source, True, text, start_s, start_s + 1.0))


class _Profiles:
    def system_prompt(self, context: str) -> str:
        return f"reglas {context}"


class _Context:
    def text(self) -> str:
        return "contexto"


class _Setup:
    config = ClaudeModelConfig()
    profiles = _Profiles()
    context = _Context()


class _Owner:
    """Hilo dueño de prueba: guarda las tareas en una cola y las corre al bombear."""

    def __init__(self) -> None:
        self.thread = threading.current_thread()
        self._tasks: queue.Queue = queue.Queue()

    def post(self, task) -> None:
        self._tasks.put(task)

    def pump_until(self, condition, timeout_s: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_s
        while not condition():
            with contextlib.suppress(queue.Empty):
                self._tasks.get(timeout=0.01)()
            if time.monotonic() > deadline:
                raise AssertionError("se agotó la espera")


def _recording(threads: set, **names):
    """Callbacks que anotan en qué hilo llegaron."""
    return {
        name: (lambda *_args, out=out: (threads.add(threading.current_thread()), out.append(1)))
        for name, out in names.items()
    }


def test_agent_sends_a_range_and_streams_in_the_owner_thread():
    owner, threads, turns = _Owner(), set(), []
    service = ScriptedClaude(["Con gusto, ", "claro."])
    agent = AgentAssistant(_Live(), _Setup(), lambda _config, _prompt: service)
    agent.attach(owner.post, AgentListeners(**_recording(threads, turns=turns)))
    agent.mark_start(0, 0)
    agent.mark_end(0, 99)
    assert agent.busy and agent.logic.state is AgentState.SENDING
    owner.pump_until(lambda: not agent.busy)
    assert agent.turns[0].answer == "Con gusto, claro."
    assert agent.logic.state is AgentState.ANSWERED
    assert "<cliente>\n[09:00:00] buenas tardes" in service.prompts[0]
    assert threads == {owner.thread}
    agent.close()


def test_ahead_pulse_sends_after_the_silence_without_qt():
    owner, now = _Owner(), [100.0]
    live = _Live()
    service = ScriptedClaude(["4."])
    agent = AgentAssistant(live, _Setup(), lambda _config, _prompt: service, clock=lambda: now[0])
    agent.attach(owner.post, AgentListeners())
    agent.set_mode(AHEAD)
    live.say("ellos", "¿cuánto es dos por dos?", 10.0)
    agent.on_transcript("ellos")
    now[0] = 102.0  # pasó el silencio: el pulso (no la prueba) lo envía
    owner.pump_until(lambda: service.prompts and not agent.busy)
    assert "dos por dos" in service.prompts[0].split("Su último turno:")[1]
    assert agent.turns[0].answer == "4."
    agent.set_mode(MANUAL)
    agent.close()


def test_chat_sends_and_reports_sending_in_the_owner_thread():
    owner, threads = _Owner(), set()
    sending: list[bool] = []
    service = ScriptedClaude(["Listo."])
    chat = ChatAssistant(_Live(), _Setup(), service_factory=lambda _config, _prompt: service)
    listeners = ChatListeners(**_recording(threads, turns=[]))
    listeners.sending = lambda value: (
        threads.add(threading.current_thread()),
        sending.append(value),
    )
    chat.attach(owner.post, listeners)
    assert chat.send("resume lo dicho")
    owner.pump_until(lambda: not chat.sending)
    assert chat.turns[0].answer == "Listo."
    assert sending == [True, False]
    assert "buenas tardes" in service.prompts[0] and "resume lo dicho" in service.prompts[0]
    assert threads == {owner.thread}
    chat.close()
