"""La escucha por la API: guardia, rutas y canal SSE con motor y captura falsos (sin GPU)."""

from __future__ import annotations

import json
import logging
import time

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="extra web: pip install -e '../jacck_common[webapi]'")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.live import LiveListening  # noqa: E402
from domain.transcription.engine import TranscriptEvent  # noqa: E402
from entrypoints.api.run import VITE_PORT, create_api  # noqa: E402

BLOCK = np.zeros(1_600, dtype=np.float32)
DEVICES = {"tu": "mic.sintetico"}


class _OpenCapture:
    """Tres bloques sintéticos al arrancar; sigue viva hasta que la escucha la detiene."""

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
    """Un provisional con el primer bloque y un final con el tercero."""

    def __init__(self, on_event):
        self._on_event = on_event
        self.fed = 0

    def start(self):
        pass

    def feed(self, source, _samples):
        self.fed += 1
        if self.fed == 1:
            self._on_event(TranscriptEvent(source, False, "hola", 0.0, 0.1))
        if self.fed == 3:
            self._on_event(TranscriptEvent(source, True, "Hola a todos.", 0.0, 0.3))

    def stop(self):
        pass


@pytest.fixture
def listening(tmp_path):
    item = LiveListening(
        lambda on_event, *_: _FakeEngine(on_event),
        tmp_path / "transcripciones",
        capture_factory=_OpenCapture,
    )
    yield item
    item.close(5.0)


def _auth(token: str, **extra: str) -> dict:
    return {"Authorization": f"Bearer {token}", **extra}


def _until(read, condition, timeout_s: float = 5.0):
    """Lee hasta que `condition(valor)` se cumpla o venza el plazo; devuelve el último valor."""
    deadline = time.monotonic() + timeout_s
    value = read()
    while not condition(value) and time.monotonic() < deadline:
        time.sleep(0.02)
        value = read()
    return value


def _frames(text: str) -> list[tuple[int, str, dict]]:
    """(id, tipo, datos) de cada evento de un SSE; los comentarios se saltan."""
    frames = []
    for block in text.strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
        )
        if fields:
            frames.append((int(fields["id"]), fields["event"], json.loads(fields["data"])))
    return frames


def test_guard_asks_token_and_allows_only_tauri_and_this_vite(listening) -> None:
    token = new_token()
    with TestClient(create_api(token, listening), base_url="http://127.0.0.1") as client:
        assert client.get("/api/listening").status_code == 401
        assert client.post("/api/listening/stop").status_code == 401
        other = {"Origin": "https://ejemplo.com"}
        assert client.get("/api/listening", headers=_auth(token, **other)).status_code == 403
        venona = {"Origin": "http://127.0.0.1:5173"}
        assert client.get("/api/listening", headers=_auth(token, **venona)).status_code == 403
        vite = {"Origin": f"http://127.0.0.1:{VITE_PORT}"}
        assert client.get("/api/listening", headers=_auth(token, **vite)).status_code == 200
        assert client.get("/api/health", headers=_auth(token)).status_code == 200


def test_fake_listening_streams_its_phrases_and_stops(listening, tmp_path, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    token = new_token()
    headers = _auth(token)
    texts = []
    api = create_api(token, listening, keepalive=0.05)
    with TestClient(api, base_url="http://127.0.0.1") as client:

        def read() -> dict:
            response = client.get("/api/listening", headers=headers)
            texts.append(response.text)
            return response.json()

        started = client.post("/api/listening/start", headers=headers, json={"devices": DEVICES})
        texts.append(started.text)
        assert started.json()["state"] == "loading"
        state = _until(read, lambda s: s["transcript"]["tu"]["finals"])
        assert state["state"] == "listening"
        assert [line["text"] for line in state["transcript"]["tu"]["finals"]] == ["Hola a todos."]
        assert state["path"] is not None

        stopped = client.post("/api/listening/stop", headers=headers)
        texts.append(stopped.text)
        assert stopped.json()["state"] == "stopping"
        assert _until(read, lambda s: s["state"] == "stopped")["state"] == "stopped"

        copy = tmp_path / "copia.md"
        saved = client.post("/api/listening/save", headers=headers, json={"path": str(copy)})
        texts.append(saved.text)
        assert saved.status_code == 200
        assert "Hola a todos." in copy.read_text(encoding="utf-8")
        relative = client.post("/api/listening/save", headers=headers, json={"path": "a.md"})
        assert relative.status_code == 422

        # El canal vive toda la apertura; se cierra aquí para leer el SSE completo.
        api.state.listening_channel.close("closed", {})
        stream = client.get("/api/listening/events", headers=headers)
        texts.append(stream.text)
        resumed = client.get(
            "/api/listening/events", headers=_auth(token, **{"Last-Event-ID": "2"})
        )

    frames = _frames(stream.text)
    assert [seq for seq, _, _ in frames] == list(range(1, len(frames) + 1))
    kinds = [kind for _, kind, _ in frames]
    states = [data["state"] for _, kind, data in frames if kind == "state"]
    assert states == ["loading", "listening", "stopping", "stopped"]
    assert kinds.index("session") < kinds.index("phrase")
    phrases = [data for _, kind, data in frames if kind == "phrase"]
    assert phrases[0] == {
        "source": "tu",
        "final": False,
        "clock": phrases[0]["clock"],
        "text": "hola",
        "stable_words": 0,
    }
    assert phrases[-1]["final"] and phrases[-1]["text"] == "Hola a todos."
    assert kinds[-2:] == ["saved", "closed"]
    assert [seq for seq, _, _ in _frames(resumed.text)][0] == 3

    # Ninguna respuesta ni registro trae el token.
    assert all(token not in text for text in texts)
    assert all(token not in record.getMessage() for record in caplog.records)


def test_sources_keep_one_open_and_reject_unknown(listening) -> None:
    token = new_token()
    headers = _auth(token)
    with TestClient(create_api(token, listening), base_url="http://127.0.0.1") as client:
        closed = client.post("/api/listening/sources/tu", headers=headers, json={"open": False})
        assert closed.json() == {"changed": True, "closed": ["tu"]}
        last = client.post("/api/listening/sources/ellos", headers=headers, json={"open": False})
        assert last.json() == {"changed": False, "closed": ["tu"]}
        unknown = client.post("/api/listening/sources/otro", headers=headers, json={"open": True})
        assert unknown.status_code == 404
        bad = client.post("/api/listening/start", headers=headers, json={"devices": {"x": "y"}})
        assert bad.status_code == 422
        early = client.post("/api/listening/save", headers=headers, json={"path": "/tmp/a.md"})
        assert early.status_code == 409
        assert client.get("/api/listening", headers=headers).json()["last_event"] == 1


def test_second_start_resumes_and_marks_where(listening) -> None:
    """La segunda escucha de la apertura reanuda; la web pinta Reanudada con esto."""
    token = new_token()
    headers = _auth(token)
    api = create_api(token, listening, keepalive=0.05)
    with TestClient(api, base_url="http://127.0.0.1") as client:

        def read() -> dict:
            return client.get("/api/listening", headers=headers).json()

        for count in (1, 2):
            client.post("/api/listening/start", headers=headers, json={"devices": DEVICES})
            _until(read, lambda s, n=count: len(s["transcript"]["tu"]["finals"]) == n)
            client.post("/api/listening/stop", headers=headers)
            _until(read, lambda s: s["state"] == "stopped")
        state = read()
        api.state.listening_channel.close("closed", {})
        stream = client.get("/api/listening/events", headers=headers)

    marks = state["resumes"]["tu"]
    assert [mark["before"] for mark in marks] == [1]
    assert len(marks[0]["clock"]) == len("20:09")
    # Ellos no habló: su marca queda antes de su frase 0, con la misma hora.
    assert state["resumes"]["ellos"] == [{"before": 0, "clock": marks[0]["clock"]}]
    sessions = [data for _, kind, data in _frames(stream.text) if kind == "session"]
    assert sessions == [{"new": True}, {"new": False, "resumes": state["resumes"]}]
