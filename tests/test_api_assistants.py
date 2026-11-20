"""El Agente y el chat por la API, sobre una escucha falsa y un Claude con guion (sin cupo)."""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="extra web: pip install -e '../jacck_common[webapi]'")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.agent import AgentAssistant  # noqa: E402
from app.chat import ChatAssistant  # noqa: E402
from app.live import LiveListening  # noqa: E402
from domain.agent.agent_ahead import TURN_SILENCE_S  # noqa: E402
from domain.claude.claude_model import ClaudeModelConfig  # noqa: E402
from domain.transcription.engine import TranscriptEvent  # noqa: E402
from entrypoints.api.run import create_api  # noqa: E402
from services.service_claude import ScriptedClaude  # noqa: E402

BLOCK = np.zeros(1_600, dtype=np.float32)
DEVICES = {"tu": "mic.sintetico"}


class _OpenCapture:
    def __init__(self, source, _device, on_block):
        self._source = source
        self._on_block = on_block
        self.is_alive = False

    def start(self):
        self.is_alive = True
        for _ in range(3):
            self._on_block(self._source, BLOCK)

    def stop(self):
        self.is_alive = False


class _FakeEngine:
    """Un final con el tercer bloque."""

    def __init__(self, on_event):
        self._on_event = on_event
        self.fed = 0

    def start(self):
        pass

    def feed(self, source, _samples):
        self.fed += 1
        if self.fed == 3:
            self._on_event(TranscriptEvent(source, True, "Hola a todos.", 0.0, 0.3))

    def stop(self):
        pass


class _Profiles:
    def system_prompt(self, context: str = "") -> str:
        return f"reglas {context}"


class _Context:
    def text(self) -> str:
        return "contexto"


class _Setup:
    config = ClaudeModelConfig()
    profiles = _Profiles()
    context = _Context()


@pytest.fixture
def parts(tmp_path):
    listening = LiveListening(
        lambda on_event, *_: _FakeEngine(on_event), tmp_path, capture_factory=_OpenCapture
    )
    agent = AgentAssistant(
        listening, _Setup(), lambda _config, _prompt: ScriptedClaude(["Con gusto, ", "claro."])
    )
    chat = ChatAssistant(
        listening, _Setup(), service_factory=lambda _config, _prompt: ScriptedClaude(["Listo."])
    )
    yield listening, agent, chat
    agent.close()
    chat.close()
    listening.close(5.0)


def _until(read, condition, timeout_s: float = 5.0):
    deadline = time.monotonic() + timeout_s
    value = read()
    while not condition(value) and time.monotonic() < deadline:
        time.sleep(0.02)
        value = read()
    return value


def _kinds(text: str) -> list[tuple[str, dict]]:
    frames = []
    for block in text.strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
        )
        if fields:
            frames.append((fields["event"], json.loads(fields["data"])))
    return frames


def _client(parts, token):
    listening, agent, chat = parts
    api = create_api(token, listening, agent, chat, keepalive=0.05)
    return api, TestClient(api, base_url="http://127.0.0.1")


def _listen_until_final(client, headers) -> None:
    client.post("/api/listening/start", headers=headers, json={"devices": DEVICES})
    _until(
        lambda: client.get("/api/listening", headers=headers).json(),
        lambda s: s["transcript"]["tu"]["finals"],
    )


def test_agent_answers_a_marked_range_through_the_api(parts) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    api, client = _client(parts, token)
    with client:
        assert (
            client.post("/api/agent/speaker", headers=headers, json={"source": "tu"}).json()[
                "speaker"
            ]
            == "tu"
        )
        _listen_until_final(client, headers)
        marked = client.post(
            "/api/agent/mark_start", headers=headers, json={"phrase": 0, "offset": 0}
        )
        assert marked.json()["start_mark"] == {"phrase": 0, "word": 0}
        client.post("/api/agent/mark_end", headers=headers, json={"phrase": 0, "offset": 5})
        state = _until(
            lambda: client.get("/api/agent", headers=headers).json(),
            lambda s: s["turns"] and s["turns"][-1]["done"],
        )
        api.state.agent_channel.close("closed", {})
        stream = client.get("/api/agent/events", headers=headers).text

    turn = state["turns"][-1]
    assert turn["answer"] == "Con gusto, claro."
    assert "Hola a todos." in turn["fragment"]
    assert state["state"] == "answered"
    # El rango va por frases completas: termina en la última palabra de la frase.
    assert state["sent"]["tu"] == [[{"phrase": 0, "word": 0}, {"phrase": 0, "word": 2}]]
    frames = _kinds(stream)
    kinds = [kind for kind, _ in frames]
    assert {"state", "marks", "turns", "budget"} <= set(kinds)
    last_turns = [data for kind, data in frames if kind == "turns"][-1]
    assert last_turns["count"] == 1 and last_turns["last"]["done"]


def test_ahead_mode_sends_after_the_turn_through_the_loop(parts) -> None:
    """El pulso del anticipado entrega `tick` al bucle de la API: envía sin ningún clic."""
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    _, client = _client(parts, token)
    with client:
        client.post("/api/agent/speaker", headers=headers, json={"source": "tu"})
        mode = client.post("/api/agent/mode", headers=headers, json={"mode": "ahead"})
        assert mode.json()["mode"] == "ahead"
        snapshot = client.get("/api/agent", headers=headers).json()
        assert snapshot["mode"] == "ahead"
        assert snapshot["turn_silence_s"] == TURN_SILENCE_S
        _listen_until_final(client, headers)
        state = _until(
            lambda: client.get("/api/agent", headers=headers).json(),
            lambda s: s["turns"] and s["turns"][-1]["done"],
            timeout_s=8.0,
        )
    assert state["turns"][-1]["mode"] == "ahead"
    assert state["turns"][-1]["answer"] == "Con gusto, claro."


def test_agent_rejects_unknown_mode_and_speaker(parts) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    _, client = _client(parts, token)
    with client:
        assert (
            client.post("/api/agent/mode", headers=headers, json={"mode": "x"}).status_code == 422
        )
        bad = client.post("/api/agent/speaker", headers=headers, json={"source": "x"})
        assert bad.status_code == 404
        assert client.get("/api/agent").status_code == 401


def test_chat_answers_and_reports_sending(parts) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    api, client = _client(parts, token)
    with client:
        sent = client.post("/api/chat/send", headers=headers, json={"text": "¿Qué dijeron?"})
        assert sent.json()["sent"] is True
        state = _until(
            lambda: client.get("/api/chat", headers=headers).json(),
            lambda s: s["turns"] and s["turns"][-1]["done"] and not s["sending"],
        )
        assert client.post("/api/chat/send", headers=headers, json={"text": ""}).status_code == 422
        api.state.chat_channel.close("closed", {})
        stream = client.get("/api/chat/events", headers=headers).text

    assert state["turns"][-1]["answer"] == "Listo."
    assert state["turns"][-1]["request"] == "¿Qué dijeron?"
    sending = [data["sending"] for kind, data in _kinds(stream) if kind == "sending"]
    assert sending == [True, False]
