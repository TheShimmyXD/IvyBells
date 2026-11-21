from __future__ import annotations

import contextlib
import queue
import threading
import time

import numpy as np

from app.live import ListeningRun, LiveListeners, LiveListening, RunCallbacks
from domain.transcription.engine import TranscriptEvent
from domain.transcription.live_state import LiveState
from services.service_transcript import TranscriptWriter

BLOCK = np.zeros(1_600, dtype=np.float32)


class _FakeCapture:
    """Entrega tres bloques sintéticos al arrancar y queda detenida."""

    def __init__(self, source, _device, on_block):
        self._source = source
        self._on_block = on_block
        self.is_alive = False

    def start(self):
        for _ in range(3):
            self._on_block(self._source, BLOCK)

    def stop(self):
        pass


class _OpenCapture(_FakeCapture):
    """Como `_FakeCapture`, pero sigue viva hasta que la escucha la detiene."""

    def start(self):
        self.is_alive = True
        super().start()

    def stop(self):
        self.is_alive = False


class _FakeEngine:
    """Un provisional con el primer bloque y un final con el tercero."""

    def __init__(self, on_event):
        self._on_event = on_event
        self.fed = 0
        self.stopped = False

    def start(self):
        pass

    def feed(self, source, samples):
        self.fed += 1
        if self.fed == 1:
            self._on_event(TranscriptEvent(source, False, "hola", 0.0, 0.1))
        if self.fed == 3:
            self._on_event(TranscriptEvent(source, True, "Hola a todos.", 0.0, 0.3))

    def stop(self):
        self.stopped = True


def _recorded_run(tmp_path, engine_factory, got=None):
    """Una corrida con los avisos guardados en `got` (nombre -> lista de argumentos)."""
    got = got if got is not None else {}
    names = ("loaded", "event", "latency", "failed", "finished")
    for name in names:
        got.setdefault(name, [])
    callbacks = RunCallbacks(
        **{name: (lambda *args, items=got[name]: items.append(args)) for name in names}
    )
    run = ListeningRun(
        engine_factory=engine_factory,
        model="small",
        compute_type="int8",
        devices={"tu": "mic.sintetico"},
        writer=TranscriptWriter(tmp_path),
        stop_event=threading.Event(),
        request_id=7,
        callbacks=callbacks,
        capture_factory=_FakeCapture,
    )
    return run, got


def test_run_writes_markdown_without_qt(tmp_path):
    engines = []

    def factory(on_event, _model, _compute_type):
        engines.append(_FakeEngine(on_event))
        return engines[0]

    run, got = _recorded_run(tmp_path, factory)
    run.run()

    assert len(got["loaded"]) == 1 and got["loaded"][0][1] is True
    assert [args[0].is_final for args in got["event"]] == [False, True]
    assert len(got["latency"]) == 1 and got["latency"][0][0] >= 0.0
    assert got["failed"] == []
    payload = got["finished"][0][0]
    assert payload["_request_id"] == 7 and payload["phrases"] == 1
    text = payload["path"].read_text(encoding="utf-8")
    assert "Hola a todos." in text
    # La latencia de la sesión queda al final del .md (frase de "tu" del motor falso).
    assert "\n## Latencia\n\n- Tú: mediana " in text and text.endswith("(1 frase)\n")
    assert engines[0].stopped


def test_run_reports_failure_and_still_finishes(tmp_path):
    def factory(_on_event, _model, _compute_type):
        raise RuntimeError("CUDA no disponible")

    run, got = _recorded_run(tmp_path, factory)
    run.run()

    assert got["failed"] == [("CUDA no disponible",)]
    assert got["finished"][0][0]["path"] is None


def test_channel_closed_before_the_session_never_reaches_the_engine(tmp_path):
    engines = []

    def factory(on_event, *_):
        engines.append(_FakeEngine(on_event))
        return engines[0]

    run, _ = _recorded_run(tmp_path, factory)
    run.set_source_open("tu", False)
    run.run()
    assert engines[0].fed == 0
    assert engines[0].stopped


class _CountingEngine:
    """Un final por bloque; con `on_last` llama algo en el último (por ejemplo, Guardar)."""

    def __init__(self, on_event, finals, on_last=None):
        self._on_event = on_event
        self._finals = finals
        self._on_last = on_last
        self.fed = 0

    def start(self):
        pass

    def feed(self, source, _samples):
        self.fed += 1
        if self.fed <= self._finals:
            text = f"Frase {self.fed}."
            self._on_event(TranscriptEvent(source, True, text, float(self.fed), self.fed + 0.5))
        if self.fed == 3 and self._on_last is not None:
            self._on_last()

    def stop(self):
        pass


def test_stop_and_start_keep_one_markdown_and_save_while_listening(tmp_path):
    """Iniciar, 3 frases, fin, Iniciar, 2 frases y Guardar con la escucha corriendo."""
    plans = []

    def factory(on_event, *_):
        return _CountingEngine(on_event, *plans.pop(0))

    listening = LiveListening(factory, tmp_path / "t", capture_factory=_FakeCapture)
    started = []
    listening.listeners = LiveListeners(session_started=lambda: started.append(True))
    copy = tmp_path / "copia.md"
    saved = []

    plans.append((3,))
    listening.start("small", {"tu": "mic.sintetico"})
    assert listening.wait(5.0)
    plans.append((2, lambda: saved.append(listening.save_copy(copy))))
    listening.start("small", {"tu": "otro.mic"})
    assert listening.wait(5.0)
    listening.close()

    assert saved == [True] and started == [True]
    text = copy.read_text(encoding="utf-8")
    assert text.count("# Transcripción ") == 1
    assert sum(line.startswith("- **") for line in text.splitlines()) == 5
    assert "\n## Reanudada " in text and "- Tú: `otro.mic`" in text
    # La pantalla tampoco se borró: las 5 frases siguen en la columna.
    assert len(listening.transcript.finals("tu")) == 5
    assert listening.last_path is not None and listening.last_path.parent == tmp_path / "t"


def test_start_without_devices_fails_without_a_thread(tmp_path):
    listening = LiveListening(lambda *_: None, tmp_path)
    states = []
    listening.listeners = LiveListeners(state=states.append)
    listening.start("small", {})
    assert states[0]["state"] is LiveState.ERROR
    assert listening.wait(0.0)


def test_notices_arrive_in_the_owner_thread_in_order(tmp_path):
    """El hilo de la escucha avisa; los avisos salen en el hilo dueño (el de la API)."""

    def factory(on_event, *_):
        return _FakeEngine(on_event)

    tasks: queue.Queue = queue.Queue()
    owner = threading.current_thread()
    seen = {"threads": set(), "states": [], "sources": []}

    def on_state(payload):
        seen["threads"].add(threading.current_thread())
        seen["states"].append(payload["state"])

    def on_transcript(source):
        seen["threads"].add(threading.current_thread())
        seen["sources"].append(source)

    def drain_until(condition, timeout_s=5.0):
        deadline = time.monotonic() + timeout_s
        while not condition() and time.monotonic() < deadline:
            with contextlib.suppress(queue.Empty):
                tasks.get(timeout=0.01)()
        return condition()

    listening = LiveListening(factory, tmp_path, capture_factory=_OpenCapture)
    listening.attach(tasks.put, LiveListeners(state=on_state, transcript=on_transcript))
    listening.start("small", {"tu": "mic.sintetico"})
    assert drain_until(lambda: len(listening.transcript.finals("tu")) == 1)
    listening.stop()
    assert listening.wait(5.0)
    assert drain_until(lambda: seen["states"][-1:] == [LiveState.STOPPED])
    listening.close()

    assert seen["threads"] == {owner}
    assert seen["states"] == [
        LiveState.LOADING,
        LiveState.LISTENING,
        LiveState.STOPPING,
        LiveState.STOPPED,
    ]
    assert "tu" in seen["sources"]


def test_console_prints_finals_and_saves_markdown(tmp_path):
    """La consola usa la misma escucha: imprime el final con su hora y deja el `.md`."""
    from entrypoints.cli.live import ConsolePrinter, run_listening

    listening = LiveListening(
        lambda on_event, *_: _FakeEngine(on_event), tmp_path, capture_factory=_OpenCapture
    )
    out = []
    ctrl_c = threading.Event()

    def write(text):
        out.append(text)
        ctrl_c.set()

    printer = ConsolePrinter(listening.transcript.clock, write, interactive=False)
    code = run_listening(listening, "small", "int8", {"tu": "mic"}, ctrl_c, printer)

    assert code == 0
    assert len(out) == 1 and out[0].endswith("] Tú: Hola a todos.\n")
    assert "Hola a todos." in listening.last_path.read_text(encoding="utf-8")


def test_console_returns_one_when_the_listening_fails(tmp_path):
    from entrypoints.cli.live import ConsolePrinter, run_listening

    def factory(*_):
        raise RuntimeError("sin GPU")

    listening = LiveListening(factory, tmp_path, capture_factory=_FakeCapture)
    printer = ConsolePrinter(listening.transcript.clock, lambda _text: None, interactive=False)
    assert run_listening(listening, "small", "int8", {"tu": "mic"}, threading.Event(), printer) == 1


def _choices():
    from services.service_pipewire import AudioSource, CaptureSources, SourceChoices

    def source(name):
        return AudioSource(0, name, "PipeWire", "s16le 2ch 48000Hz", "IDLE")

    monitor, mic, usb = source("salida.monitor"), source("mic.interno"), source("mic.usb")
    return SourceChoices([monitor], [mic, usb], CaptureSources(monitor=monitor, microphone=mic))


def test_chosen_devices_follow_the_window_rules(tmp_path):
    """La elegida si está conectada; si no, la predeterminada (como los combos de Qt)."""
    listening = LiveListening(lambda *_: None, tmp_path)
    listening.read_sources = _choices
    assert listening.chosen_devices({}) == {"ellos": "salida.monitor", "tu": "mic.interno"}
    assert listening.chosen_devices({"tu": "mic.usb"})["tu"] == "mic.usb"
    assert listening.chosen_devices({"tu": "mic.desconectado"})["tu"] == "mic.interno"
