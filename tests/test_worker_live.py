from __future__ import annotations

import threading

import numpy as np

from coordinator_live import LiveCoordinator
from core.engine import TranscriptEvent
from services.service_transcript import TranscriptWriter
from workers.worker_live import LiveWorker

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


def _worker(tmp_path, engine_factory, writer=None, devices=None):
    return LiveWorker(
        engine_factory=engine_factory,
        model="small",
        compute_type="int8",
        devices=devices or {"tu": "mic.sintetico"},
        writer=writer or TranscriptWriter(tmp_path),
        stop_event=threading.Event(),
        request_id=7,
        capture_factory=_FakeCapture,
    )


def test_worker_runs_session_and_writes_markdown(qapp, tmp_path):
    engines = []

    def factory(on_event, _model, _compute_type):
        engines.append(_FakeEngine(on_event))
        return engines[0]

    worker = _worker(tmp_path, factory)
    got = {"loaded": [], "event": [], "latency": [], "failed": [], "finished": []}
    for name, items in got.items():
        getattr(worker, name).connect(lambda *args, items=items: items.append(args))
    worker.run()

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


def test_worker_reports_failure_and_still_finishes(qapp, tmp_path):
    def factory(_on_event, _model, _compute_type):
        raise RuntimeError("CUDA no disponible")

    worker = _worker(tmp_path, factory)
    failed, finished = [], []
    worker.failed.connect(failed.append)
    worker.finished.connect(finished.append)
    worker.run()

    assert failed == ["CUDA no disponible"]
    assert finished[0]["path"] is None


def test_channel_closed_before_the_session_never_reaches_the_engine(qapp, tmp_path):
    engines = []

    def factory(on_event, *_):
        engines.append(_FakeEngine(on_event))
        return engines[0]

    worker = _worker(tmp_path, factory)
    worker.set_source_open("tu", False)
    worker.run()
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


def test_stop_and_start_keep_one_markdown_and_save_while_listening(qapp, tmp_path):
    """Iniciar, 3 frases, Detener, Iniciar, 2 frases y Guardar con la escucha corriendo."""
    coordinator = LiveCoordinator(transcripts_dir=tmp_path / "t")
    started = []
    coordinator.session_started.connect(lambda: started.append(True))
    copy = tmp_path / "copia.md"
    saved = []

    def run(finals, on_last=None, devices=None):
        def factory(on_event, *_):
            return _CountingEngine(on_event, finals, on_last)

        worker = _worker(tmp_path, factory, coordinator.writer, devices)
        worker.loaded.connect(coordinator.on_loaded)
        worker.event.connect(coordinator.on_event)
        worker.run()

    run(3)
    run(2, lambda: saved.append(coordinator.save_copy(copy)), {"tu": "otro.mic"})
    coordinator.close()

    assert saved == [True] and started == [True]
    text = copy.read_text(encoding="utf-8")
    assert text.count("# Transcripción ") == 1
    assert sum(line.startswith("- **") for line in text.splitlines()) == 5
    assert "\n## Reanudada " in text and "- Tú: `otro.mic`" in text
    # La pantalla tampoco se borró: las 5 frases siguen en la columna.
    assert len(coordinator.transcript.finals("tu")) == 5
    assert coordinator.last_path is not None and coordinator.last_path.parent == tmp_path / "t"
