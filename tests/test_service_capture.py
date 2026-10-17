from __future__ import annotations

import sys
import threading

import numpy as np

from services.service_capture import AudioCapture, parec_command, pcm16_to_float32
from services.service_live import LiveSession


def test_pcm16_conversion_and_odd_byte():
    data = np.array([0, 16384, -32768], dtype="<i2").tobytes() + b"\x01"
    assert pcm16_to_float32(data).tolist() == [0.0, 0.5, -1.0]


def test_parec_command_picks_device_by_name():
    command = parec_command("alsa_output.x.monitor")
    assert command[:3] == ["parec", "-d", "alsa_output.x.monitor"]
    assert "--rate=16000" in command and "--channels=1" in command


def test_capture_reads_blocks_from_subprocess():
    # 0,25 s de PCM sintético: dos bloques de 100 ms y un resto de 50 ms.
    script = "import sys; sys.stdout.buffer.write(bytes(range(256)) * 31 + bytes(64))"
    blocks: list[np.ndarray] = []
    capture = AudioCapture(
        "ellos", "fake", lambda _s, b: blocks.append(b), [sys.executable, "-c", script]
    )
    capture.start()
    capture._thread.join(timeout=5)
    capture.stop()
    assert [len(block) for block in blocks] == [1600, 1600, 800]


class _FakeCapture:
    """Entrega de una vez los bloques preparados para su fuente."""

    planned: dict[str, list[np.ndarray]] = {}

    def __init__(self, source, device, on_block):
        self.source, self._on_block = source, on_block
        self.is_alive = False
        self.stopped = False

    def start(self):
        for block in self.planned[self.source]:
            self._on_block(self.source, block)

    def stop(self):
        self.stopped = True


class _FakeEngine:
    def __init__(self):
        self.fed: list[tuple[str, float]] = []
        self.stopped = False

    def feed(self, source, samples):
        assert not self.stopped
        self.fed.append((source, float(samples[0])))

    def stop(self):
        self.stopped = True


def test_session_feeds_in_order_and_stops_engine_when_captures_end():
    _FakeCapture.planned = {
        "ellos": [np.full(4, value, np.float32) for value in (1, 2, 3)],
        "tu": [np.full(4, value, np.float32) for value in (7, 8)],
    }
    engine = _FakeEngine()
    LiveSession(engine, {"ellos": "m", "tu": "mic"}, _FakeCapture).run(threading.Event())
    assert [value for source, value in engine.fed if source == "ellos"] == [1, 2, 3]
    assert [value for source, value in engine.fed if source == "tu"] == [7, 8]
    assert engine.stopped


def test_session_drains_queue_after_stop_event():
    _FakeCapture.planned = {"ellos": [np.full(4, value, np.float32) for value in (1, 2)]}
    engine = _FakeEngine()
    stop = threading.Event()
    stop.set()
    LiveSession(engine, {"ellos": "m"}, _FakeCapture).run(stop)
    assert engine.fed == [("ellos", 1.0), ("ellos", 2.0)]
    assert engine.stopped
