"""El .md de la web es el que escribia Qt (FW.10).

Una escucha falsa pasa por la API (iniciar, detener, reanudar, guardar) y su .md, con horas
y cifras medidas igualadas, debe ser el que escribia Qt con la misma escucha, guardado en
`fixtures/parity/markdown_qt.md` (2026-11-20, antes de retirar Qt): modelo, canales,
Reanudada y pie de latencia.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="extra web: ./install.sh (jacck_common)")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.live import LiveListening  # noqa: E402
from domain.transcription.engine import TranscriptEvent  # noqa: E402
from entrypoints.api.run import create_api  # noqa: E402

QT_MARKDOWN = Path(__file__).parent / "fixtures/parity/markdown_qt.md"
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


def test_web_writes_the_markdown_that_qt_wrote(tmp_path) -> None:
    web = _web_markdown(tmp_path)
    for phrase in PHRASES.values():
        assert phrase in web
    assert "## Latencia" in web
    assert "## Reanudada" in web
    assert _normalized(web) == QT_MARKDOWN.read_text(encoding="utf-8"), (
        "el .md de la web ya no es el que escribia Qt"
    )
