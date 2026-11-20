"""
Banco del SSE: cuánto agrega la API a cada frase, del motor a la interfaz (FW.4).

Uso (desde la raíz del proyecto):
    .venv/bin/python -m bench.bench_sse
    .venv/bin/python -m bench.bench_sse --phrases 20 --sin-guardar

Sin GPU, sin audio y sin Claude: una captura falsa entrega un bloque cada 100 ms (como
`parec`) y un motor falso responde a cada bloque con un provisional, otro provisional y el
final de una frase, anotando el instante justo antes de avisar. La API corre de verdad
(uvicorn por TCP en 127.0.0.1) y un cliente lee `/api/listening/events` con `httpx`;
la diferencia entre los dos instantes (mismo proceso, mismo reloj) es lo que el SSE agrega:
el paso al bucle de la API, el canal, el hilo que espera eventos y el HTTP.

Dos escenarios: `uno` (solo el canal de la escucha) y `tres` (además los del Agente y el
chat abiertos, como la interfaz web, con el Agente oyendo la transcripción).
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import socket
import tempfile
import threading
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import httpx
import numpy as np
import uvicorn
from jacck_common.webapi.security import new_token

from app.agent import AgentAssistant
from app.chat import ChatAssistant
from app.context import ContextLibrary
from app.live import LiveListening
from app.profiles import ProfileLibrary
from app.settings import ClaudeOptions
from domain.bench.bench_metrics import median_s, percentile
from domain.transcription.engine import TranscriptEvent
from domain.transcription.live_state import LiveState
from entrypoints.api.run import create_api
from logging_config import LOG_FORMAT
from paths import BENCH_RESULTS_DIR
from services.service_claude import ScriptedClaude
from services.service_contexts import ContextStore
from services.service_profiles import ProfileStore

logger = logging.getLogger("bench_sse")

BLOCK_S = 0.1
BLOCK = np.zeros(1_600, dtype=np.float32)
SOURCE = "ellos"
# Bloques por frase: dos provisionales y el final.
STEPS = 3
GOAL_P90_MS = 50.0
STOPPED = LiveState.STOPPED.value


class _TimedCapture:
    """Un bloque cada `BLOCK_S`, en su hilo, hasta que se detenga."""

    def __init__(self, source, _device, on_block):
        self._source = source
        self._on_block = on_block
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.is_alive = False

    def start(self):
        self.is_alive = True
        self._thread = threading.Thread(target=self._run, name="bench-captura", daemon=True)
        self._thread.start()

    def _run(self):
        next_at = time.perf_counter()
        while not self._stop.is_set():
            self._on_block(self._source, BLOCK)
            next_at += BLOCK_S
            self._stop.wait(max(0.0, next_at - time.perf_counter()))

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(2.0)
        self.is_alive = False


class _StampedEngine:
    """Provisional, provisional y final por frase; anota cuándo avisa cada evento."""

    def __init__(self, on_event, stamps: dict[str, float], phrases: int):
        self._on_event = on_event
        self._stamps = stamps
        self._phrases = phrases
        self.fed = 0

    def start(self):
        pass

    def feed(self, source, _samples):
        index, step = divmod(self.fed, STEPS)
        self.fed += 1
        if index >= self._phrases:
            return
        words = ["Frase", f"{index:04d}", "de", "prueba", "del", "canal"]
        final = step == STEPS - 1
        shown = words if final else words[: 2 + 2 * step]
        text = " ".join(shown) + ("." if final else "")
        key = f"{'F' if final else 'P'}|{text}"
        start = index * STEPS * BLOCK_S
        event = TranscriptEvent(source, final, text, start, start + STEPS * BLOCK_S)
        self._stamps[key] = time.perf_counter()
        self._on_event(event)

    def stop(self):
        pass


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _options(folder: Path) -> ClaudeOptions:
    profiles = folder / "perfiles"
    profiles.mkdir()
    (profiles / "ejemplo.md").write_text("Perfil de ejemplo.", encoding="utf-8")
    (folder / "contextos").mkdir()
    return ClaudeOptions(
        profiles=ProfileLibrary(ProfileStore(profiles)),
        context=ContextLibrary(
            target=folder / "contexto.md", store=ContextStore(folder / "contextos")
        ),
        accounts_dir=folder / "cuentas",
    )


def _read_phrases(url: str, headers: dict, arrived: dict[str, float], ready: threading.Event):
    """Lee el SSE de la escucha y anota cuándo llega cada frase."""
    kind = ""
    with httpx.stream("GET", url, headers=headers, timeout=None) as response:
        ready.set()
        for line in response.iter_lines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: ") and kind == "phrase":
                now = time.perf_counter()
                data = json.loads(line[6:])
                arrived[f"{'F' if data['final'] else 'P'}|{data['text']}"] = now
            elif line.startswith("data: ") and kind == "closed":
                return


def _drain(url: str, headers: dict, ready: threading.Event, counted: list[int]) -> None:
    """Otro canal abierto (Agente o chat): solo cuenta lo que llega."""
    with httpx.stream("GET", url, headers=headers, timeout=None) as response:
        ready.set()
        for line in response.iter_lines():
            if line.startswith("event: "):
                counted[0] += 1
                if line == "event: closed":
                    return


def run_scenario(name: str, phrases: int, extra_channels: bool) -> dict:
    stamps: dict[str, float] = {}
    arrived: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix="ivybells-bench-sse-") as tmp:
        folder = Path(tmp)
        listening = LiveListening(
            lambda on_event, *_: _StampedEngine(on_event, stamps, phrases),
            folder / "transcripciones",
            capture_factory=_TimedCapture,
        )
        options = _options(folder)
        agent = AgentAssistant(listening, options, lambda *_: ScriptedClaude(["Hola."]))
        chat = ChatAssistant(listening, options, service_factory=lambda *_: ScriptedClaude(["Ok."]))
        token = new_token()
        api = create_api(token, listening, agent, chat, options=options)
        port = _free_port()
        server = uvicorn.Server(
            uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning")
        )
        serving = threading.Thread(target=server.run, name="bench-uvicorn", daemon=True)
        serving.start()
        while not server.started:
            time.sleep(0.01)
        base = f"http://127.0.0.1:{port}"
        headers = {"Authorization": f"Bearer {token}"}

        readers: list[threading.Thread] = []
        ready = [threading.Event()]
        readers.append(
            threading.Thread(
                target=_read_phrases,
                args=(f"{base}/api/listening/events", headers, arrived, ready[0]),
                daemon=True,
            )
        )
        others = [0]
        if extra_channels:
            for path in ("/api/agent/events", "/api/chat/events"):
                ready.append(threading.Event())
                readers.append(
                    threading.Thread(
                        target=_drain,
                        args=(f"{base}{path}", headers, ready[-1], others),
                        daemon=True,
                    )
                )
        for reader in readers:
            reader.start()
        for flag in ready:
            flag.wait(10)

        started = time.perf_counter()
        httpx.post(
            f"{base}/api/listening/start",
            headers=headers,
            json={"devices": {SOURCE: "bench.sintetico"}},
        )
        expected = phrases * STEPS
        deadline = started + phrases * STEPS * BLOCK_S + 30
        while len(arrived) < expected and time.perf_counter() < deadline:
            time.sleep(0.05)
        httpx.post(f"{base}/api/listening/stop", headers=headers)
        # El aviso de "detenida" llega después: el canal se cierra cuando ya pasó.
        until = time.perf_counter() + 10
        while time.perf_counter() < until:
            state = httpx.get(f"{base}/api/listening", headers=headers).json()["state"]
            if state == STOPPED:
                break
            time.sleep(0.05)
        api.state.listening_channel.close("closed", {})
        if extra_channels:
            api.state.agent_channel.close("closed", {})
            api.state.chat_channel.close("closed", {})
        for reader in readers:
            reader.join(5)
        server.should_exit = True
        serving.join(10)
        agent.close()
        chat.close()
        options.close()
        listening.close(5.0)

    return _summarize(name, stamps, arrived, expected, others[0], extra_channels)


def _summarize(name, stamps, arrived, expected, others, extra_channels) -> dict:
    def delays(prefix: str) -> list[float]:
        return [
            arrived[key] - stamps[key]
            for key in stamps
            if key.startswith(prefix) and key in arrived
        ]

    finals, partials = delays("F|"), delays("P|")
    every = finals + partials

    def ms(values: list[float], fraction: float | None = None) -> float | None:
        if not values:
            return None
        value = median_s(values) if fraction is None else percentile(values, fraction)
        return round(value * 1000, 2)

    return {
        "escenario": name,
        "canales_extra": ["agent", "chat"] if extra_channels else [],
        "eventos_esperados": expected,
        "eventos_recibidos": len(arrived),
        "eventos_otros_canales": others,
        "finales": {
            "n": len(finals),
            "mediana_ms": ms(finals),
            "p90_ms": ms(finals, 0.9),
            "max_ms": None if not finals else round(max(finals) * 1000, 2),
        },
        "todos": {
            "n": len(every),
            "mediana_ms": ms(every),
            "p90_ms": ms(every, 0.9),
            "p99_ms": ms(every, 0.99),
            "max_ms": None if not every else round(max(every) * 1000, 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Banco del SSE de la API de IvyBells")
    parser.add_argument("--phrases", type=int, default=200, help="frases finales por escenario")
    parser.add_argument("--sin-guardar", action="store_true", help="solo muestra las cifras")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)
    logger.setLevel(logging.INFO)

    scenarios = [
        run_scenario("uno", args.phrases, extra_channels=False),
        run_scenario("tres", args.phrases, extra_channels=True),
    ]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    report = {
        "fecha": stamp,
        "equipo": {"python": platform.python_version(), "sistema": platform.platform()},
        "versiones": {pkg: version(pkg) for pkg in ("fastapi", "starlette", "uvicorn", "httpx")},
        "opciones": {"bloque_s": BLOCK_S, "eventos_por_frase": STEPS, "frases": args.phrases},
        "objetivo_p90_ms": GOAL_P90_MS,
        "escenarios": scenarios,
    }
    for row in scenarios:
        final, every = row["finales"], row["todos"]
        logger.info(
            "%s: finales n=%s mediana %s ms, p90 %s ms, max %s ms; todos p90 %s ms, p99 %s ms; "
            "recibidos %s/%s; otros canales %s",
            row["escenario"],
            final["n"],
            final["mediana_ms"],
            final["p90_ms"],
            final["max_ms"],
            every["p90_ms"],
            every["p99_ms"],
            row["eventos_recibidos"],
            row["eventos_esperados"],
            row["eventos_otros_canales"],
        )
    if args.sin_guardar:
        return
    BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = BENCH_RESULTS_DIR / f"{stamp}_sse.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Guardado en bench/resultados/%s", path.name)


if __name__ == "__main__":
    main()
