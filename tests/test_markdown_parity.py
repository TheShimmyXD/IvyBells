"""El .md de la web es el de Qt: la misma escucha falsa por las dos puertas da el mismo texto.

Las dos puertas escriben con `LiveListening`; esta prueba cuida que ninguna arranque,
detenga o guarde de otra forma (modelo, canales, Reanudada, pie de latencia). Solo se
igualan las horas y las cifras medidas, que cambian de una corrida a otra.
"""

from __future__ import annotations

import re
import time

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="extra web: pip install -e '../jacck_common[webapi]'")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.live import LiveListening  # noqa: E402
from domain.transcription.engine import TranscriptEvent  # noqa: E402
from domain.transcription.live_state import LiveState  # noqa: E402
from entrypoints.api.run import create_api  # noqa: E402
from entrypoints.ui_qt.coordinators.coordinator_live import LiveCoordinator  # noqa: E402

BLOCK = np.zeros(1_600, dtype=np.float32)
MODEL = "small"
DEVICES = {"ellos": "parlantes.sintetico.monitor", "tu": "mic.sintetico"}
PHRASES = {"ellos": "Buenos días a todos.", "tu": "Hola, ¿me escuchan?"}
TIMEOUT_S = 5.0
# Iniciar y detener dos veces: la segunda reanuda el mismo .md.
ROUNDS = (1, 2)


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
    """Por canal: un provisional con el primer bloque y su frase final con el tercero."""

    def __init__(self, on_event):
        self._on_event = on_event
        self._fed: dict[str, int] = {}

    def start(self):
        pass

    def feed(self, source, _samples):
        count = self._fed[source] = self._fed.get(source, 0) + 1
        if count == 1:
            self._on_event(TranscriptEvent(source, False, "...", 0.0, 0.1))
        if count == 3:
            self._on_event(TranscriptEvent(source, True, PHRASES[source], 0.0, 0.3))

    def stop(self):
        pass


def _listening(folder):
    return LiveListening(
        lambda on_event, *_: _FakeEngine(on_event), folder, capture_factory=_OpenCapture
    )


def _wait(condition, step=lambda: time.sleep(0.02)) -> bool:
    deadline = time.monotonic() + TIMEOUT_S
    while not condition() and time.monotonic() < deadline:
        step()
    return condition()


def _normalized(text: str) -> str:
    """Iguala horas, fechas y cifras medidas; deja palabras, orden y estructura."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "<fecha>", text)
    text = re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "<hora>", text)
    return re.sub(r"\d+([.,]\d+)?", "<n>", text)


def _web_markdown(tmp_path) -> str:
    listening = _listening(tmp_path / "web")
    headers = {"Authorization": f"Bearer {(token := new_token())}"}
    copy = tmp_path / "web.md"
    try:
        with TestClient(create_api(token, listening), base_url="http://127.0.0.1") as client:

            def state() -> dict:
                return client.get("/api/listening", headers=headers).json()

            body = {"model": MODEL, "devices": DEVICES}
            for rounds in ROUNDS:
                assert client.post("/api/listening/start", headers=headers, json=body).is_success
                assert _wait(
                    lambda rounds=rounds: all(
                        len(state()["transcript"][s]["finals"]) == rounds for s in DEVICES
                    )
                )
                assert client.post("/api/listening/stop", headers=headers).is_success
                assert _wait(lambda: state()["state"] == "stopped")
            saved = client.post("/api/listening/save", headers=headers, json={"path": str(copy)})
            assert saved.is_success
    finally:
        listening.close(TIMEOUT_S)
    return copy.read_text(encoding="utf-8")


def _qt_markdown(qapp, tmp_path) -> str:
    listening = _listening(tmp_path / "qt")
    coordinator = LiveCoordinator(listening)
    copy = tmp_path / "qt.md"
    try:
        for rounds in ROUNDS:
            coordinator.start(MODEL, DEVICES)
            assert _wait(
                lambda rounds=rounds: all(
                    len(coordinator.transcript.finals(s)) == rounds for s in DEVICES
                ),
                qapp.processEvents,
            )
            coordinator.stop()
            assert _wait(lambda: coordinator.logic.state is LiveState.STOPPED, qapp.processEvents)
        assert coordinator.save_copy(copy)
    finally:
        coordinator.close()
        listening.close(TIMEOUT_S)
    return copy.read_text(encoding="utf-8")


def test_web_and_qt_write_the_same_markdown(qapp, tmp_path) -> None:
    web = _web_markdown(tmp_path)
    qt = _qt_markdown(qapp, tmp_path)
    for phrase in PHRASES.values():
        assert phrase in web
    assert "## Latencia" in web
    assert "## Reanudada" in web
    assert _normalized(web) == _normalized(qt)
