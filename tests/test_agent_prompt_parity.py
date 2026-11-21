"""El Agente de la web arma los mismos prompts que armaba el de Qt (FW.8, FW.10).

La muestra `agent_marks.json` (compartida con Vitest) trae una conversacion inventada y lo
que la web manda a la API por cada clic sobre las burbujas. Una escucha falsa pasa por la
API y un Claude falso guarda lo que recibe; los prompts, con las horas igualadas, deben ser
los que mandaba Qt con los mismos clics, guardados en `fixtures/parity/agent_prompts_qt.json`
(2026-11-20, antes de retirar Qt).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="extra web: pip install -e '../jacck_common[webapi]'")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.agent import AgentAssistant  # noqa: E402
from app.context import ContextLibrary  # noqa: E402
from app.live import LiveListening  # noqa: E402
from app.profiles import ProfileLibrary  # noqa: E402
from app.settings import ClaudeOptions  # noqa: E402
from domain.agent.agent_state import AgentState  # noqa: E402
from domain.transcription.engine import TranscriptEvent  # noqa: E402
from entrypoints.api.run import create_api  # noqa: E402
from services.service_claude import ScriptedClaude  # noqa: E402
from services.service_contexts import ContextStore  # noqa: E402
from services.service_profiles import ProfileStore  # noqa: E402

SAMPLE = json.loads(
    (Path(__file__).parents[1] / "web/src/features/live/fixtures/agent_marks.json").read_text(
        encoding="utf-8"
    )
)
QT_PROMPTS = Path(__file__).parent / "fixtures/parity/agent_prompts_qt.json"
BLOCK = np.zeros(1_600, dtype=np.float32)
MODEL = "small"
DEVICES = {"ellos": "parlantes.sintetico.monitor", "tu": "mic.sintetico"}
ANSWERS = ["Con gusto, ", "el plan anual cuesta..."]
TIMEOUT_S = 5.0


class _OpenCapture:
    """Un bloque sintético al arrancar; sigue viva hasta que la escucha la detiene."""

    def __init__(self, source, _device, on_block):
        self._source = source
        self._on_block = on_block
        self.is_alive = False

    def start(self):
        self.is_alive = True
        self._on_block(self._source, BLOCK)

    def stop(self):
        self.is_alive = False


class _FakeEngine:
    """Con el primer bloque de cada canal suelta todas sus frases finales de la muestra."""

    def __init__(self, on_event):
        self._on_event = on_event
        self._done: set[str] = set()

    def start(self):
        pass

    def feed(self, source, _samples):
        if source in self._done:
            return
        self._done.add(source)
        for line in SAMPLE["finals"][source]:
            at = line["at_s"]
            self._on_event(TranscriptEvent(source, True, line["text"], at, at + 2.0))

    def stop(self):
        pass


class _Recorder:
    """Fábrica de Claude falso que guarda el system prompt y el prompt de cada envío."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self._services: list[tuple[str, ScriptedClaude]] = []

    def __call__(self, _config, system_prompt: str) -> ScriptedClaude:
        service = ScriptedClaude(ANSWERS)
        self._services.append((system_prompt, service))
        return service

    def prompts(self) -> list[tuple[str, str]]:
        return [
            (system, prompt) for system, service in self._services for prompt in service.prompts
        ]


def _listening(folder) -> LiveListening:
    return LiveListening(
        lambda on_event, *_: _FakeEngine(on_event), folder, capture_factory=_OpenCapture
    )


def _wait(condition, step=lambda: time.sleep(0.02)) -> bool:
    deadline = time.monotonic() + TIMEOUT_S
    while not condition() and time.monotonic() < deadline:
        step()
    return condition()


def _counts() -> dict[str, int]:
    return {source: len(lines) for source, lines in SAMPLE["finals"].items()}


def _normalized(prompts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(system, re.sub(r"\d{2}:\d{2}:\d{2}", "<hora>", prompt)) for system, prompt in prompts]


def _web_prompts(tmp_path) -> list[tuple[str, str]]:
    listening = _listening(tmp_path / "web")
    recorder = _Recorder()
    # Perfiles y contexto en tmp_path: nunca los del autor.
    options = ClaudeOptions(
        profiles=ProfileLibrary(ProfileStore(tmp_path / "profiles")),
        context=ContextLibrary(
            target=tmp_path / "context.md", store=ContextStore(tmp_path / "contexts")
        ),
    )
    agent = AgentAssistant(listening, options, recorder)
    headers = {"Authorization": f"Bearer {(token := new_token())}"}
    try:
        with TestClient(create_api(token, listening, agent), base_url="http://127.0.0.1") as client:

            def get(path: str) -> dict:
                return client.get(path, headers=headers).json()

            body = {"model": MODEL, "devices": DEVICES}
            assert client.post("/api/listening/start", headers=headers, json=body).is_success
            assert _wait(
                lambda: (
                    {s: len(t["finals"]) for s, t in get("/api/listening")["transcript"].items()}
                    == _counts()
                )
            )
            assert get("/api/agent")["speaker"] == SAMPLE["speaker"]
            for send in SAMPLE["sends"]:
                for request in send["requests"]:
                    sent = client.post(request["path"], headers=headers, json=request["body"])
                    assert sent.is_success
                assert _wait(lambda: get("/api/agent")["state"] == AgentState.ANSWERED)
            assert client.post("/api/listening/stop", headers=headers).is_success
    finally:
        agent.close()
        listening.close(TIMEOUT_S)
    return recorder.prompts()


def test_web_sends_the_prompts_that_qt_sent(tmp_path) -> None:
    web = _web_prompts(tmp_path)
    assert len(web) == len(SAMPLE["sends"])
    first, second = (prompt for _system, prompt in web)
    # Primer envío: las dos frases (el final quedó antes y se invierte); el segundo lleva
    # el primer intercambio como historial.
    assert "Buenas tardes." in first and "plan anual" in first
    assert "permanencia" in second and "Buenas tardes." in second
    assert "".join(ANSWERS) in second
    # Todos los envios con el mismo system prompt (reglas, perfil y contexto).
    assert len({system for system, _prompt in web}) == 1
    qt = json.loads(QT_PROMPTS.read_text(encoding="utf-8"))
    assert [prompt for _system, prompt in _normalized(web)] == qt, (
        "los prompts de la web ya no son los que mandaba Qt"
    )
