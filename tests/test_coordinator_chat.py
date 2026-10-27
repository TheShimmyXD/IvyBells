from __future__ import annotations

import time
from datetime import datetime

import pytest
from PySide6.QtCore import QObject, Signal

from core.engine import TranscriptEvent
from core.live_view import LiveTranscript
from services.service_claude import ScriptedClaude


class _FakeLive(QObject):
    """Lo que el chat usa de la escucha en vivo: solo la transcripción."""

    transcript_changed = Signal(str)

    def __init__(self, phrases: dict[str, list[str]]) -> None:
        super().__init__()
        self.closed_sources: set[str] = set()
        self.transcript = LiveTranscript()
        self.transcript.reset(datetime(2026, 10, 26, 10, 0, 0))
        for source, texts in phrases.items():
            for index, text in enumerate(texts):
                start = index * 4.0 + (2.0 if source == "tu" else 0.0)
                self.transcript.apply(TranscriptEvent(source, True, text, start, 1.0))


PHRASES = {"ellos": ["dónde está el pool", "y qué hace la línea 17"], "tu": ["en db pool"]}


def _wait(qapp, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition():
        qapp.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("se agotó la espera")
        time.sleep(0.01)


@pytest.fixture
def make(qapp, tmp_path):
    from coordinator_chat import ChatCoordinator
    from coordinator_config import ClaudeSettings
    from coordinator_context import AgentContext
    from core.claude_model import ClaudeModelConfig

    photo = tmp_path / "contexto.md"
    photo.write_text("La tabla se llama tasks.", encoding="utf-8")
    made = []

    def build(service, remembered=None, **kwargs):
        calls = []

        def factory(config, system_prompt):
            calls.append((config, system_prompt))
            return service

        settings = ClaudeSettings(
            ClaudeModelConfig(model="haiku", effort="max", account="a@b.co"),
            context=AgentContext(target=photo),
        )
        chat = ChatCoordinator(
            _FakeLive(PHRASES),
            settings,
            remember=(lambda key, value: remembered.append((key, value)))
            if remembered is not None
            else None,
            service_factory=factory,
            **kwargs,
        )
        made.append(chat)
        return chat, calls

    yield build
    for chat in made:
        chat.close()
        _wait(qapp, lambda c=chat: c._thread is None)


def test_request_carries_both_channels_and_context_without_profile(qapp, make):
    service = ScriptedClaude(["En pool.ts, ", "línea 7."])
    chat, calls = make(service, model="sonnet", effort="high")
    assert chat.send("¿dónde está el pool?")
    _wait(qapp, lambda: not chat.sending)
    turn = chat.turns[0]
    assert turn.answer == "En pool.ts, línea 7."
    assert turn.first_text_s is not None and turn.counts
    prompt = service.prompts[0]
    assert "[10:00:00] Ellos: dónde está el pool" in prompt
    assert "[10:00:02] Tú: en db pool" in prompt
    assert prompt.index("Ellos: dónde") < prompt.index("Tú: en db") < prompt.index("línea 17")
    config, system_prompt = calls[0]
    assert (config.model, config.effort, config.account) == ("sonnet", "high", "a@b.co")
    assert "La tabla se llama tasks." in system_prompt
    assert "<perfil>" not in system_prompt


def test_second_request_carries_the_chat_history(qapp, make):
    service = ScriptedClaude(["primera respuesta"])
    chat, _calls = make(service)
    chat.send("uno")
    _wait(qapp, lambda: not chat.sending)
    chat.send("dos")
    _wait(qapp, lambda: not chat.sending)
    assert "<asistente>\nprimera respuesta\n</asistente>" in service.prompts[1]
    assert "Nuestro chat" not in service.prompts[0]


def test_only_one_request_at_a_time_and_empty_is_ignored(qapp, make):
    chat, _calls = make(ScriptedClaude(["a", "b"], pause_s=0.2))
    assert not chat.send("   ")
    assert chat.send("uno")
    assert not chat.send("dos")
    assert len(chat.turns) == 1


def test_cancel_and_failure_do_not_enter_the_history(qapp, make):
    chat, _calls = make(ScriptedClaude(["a", "b", "c"], pause_s=0.2))
    chat.send("uno")
    chat.cancel()
    _wait(qapp, lambda: not chat.sending)
    assert chat.turns[0].cancelled and not chat.turns[0].counts

    failing, _calls = make(ScriptedClaude(["parcial"], error="sin cupo"))
    failing.send("dos")
    _wait(qapp, lambda: not failing.sending)
    assert failing.turns[0].error == "sin cupo" and not failing.turns[0].counts


def test_model_and_effort_are_its_own_and_remembered(qapp, make):
    remembered = []
    chat, _calls = make(ScriptedClaude(["ok"]), remembered)
    configs = []
    chat.config_changed.connect(configs.append)
    chat.set_model("opus")
    chat.set_effort("")
    chat.set_model("gpt")  # inválido: no cambia
    assert remembered == [("chat_model", "opus"), ("chat_effort", "")]
    assert (chat.config.model, chat.config.effort) == ("opus", "")
    assert chat.settings.config.model == "haiku"  # el agente no cambia
    assert [config.model for config in configs] == ["opus", "opus"]


def test_clear_empties_and_cancels(qapp, make):
    chat, _calls = make(ScriptedClaude(["a", "b"], pause_s=0.2))
    chat.send("uno")
    chat.clear()
    assert chat.turns == []
    _wait(qapp, lambda: not chat.sending)
    assert chat.turns == []
