from __future__ import annotations

import threading

import numpy as np

from core.engine import TranscriptEvent
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


def _worker(tmp_path, engine_factory):
    return LiveWorker(
        engine_factory=engine_factory,
        model="small",
        compute_type="int8",
        devices={"tu": "mic.sintetico"},
        transcripts_dir=tmp_path,
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

    assert len(got["loaded"]) == 1
    assert [args[0].is_final for args in got["event"]] == [False, True]
    assert len(got["latency"]) == 1 and got["latency"][0][0] >= 0.0
    assert got["failed"] == []
    payload = got["finished"][0][0]
    assert payload["_request_id"] == 7 and payload["phrases"] == 1
    assert "Hola a todos." in payload["path"].read_text(encoding="utf-8")
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
