"""
Sesión en vivo: las capturas de cada fuente ponen bloques en una cola y un solo hilo
(el que llama a `run`) los entrega al motor, en el orden en que llegaron.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

import numpy as np

from core.engine import TranscriptionEngine
from services.service_capture import AudioCapture, BlockCallback

logger = logging.getLogger(__name__)

QUEUE_POLL_S = 0.2

CaptureFactory = Callable[[str, str, BlockCallback], AudioCapture]


class LiveSession:
    """Une las capturas (fuente -> nombre en PipeWire) con un motor ya iniciado."""

    def __init__(
        self,
        engine: TranscriptionEngine,
        devices: dict[str, str],
        capture_factory: CaptureFactory = AudioCapture,
    ) -> None:
        self._engine = engine
        self._devices = devices
        self._capture_factory = capture_factory
        self._queue: queue.Queue[tuple[str, np.ndarray]] = queue.Queue()

    def run(self, stop_event: threading.Event) -> None:
        """
        Captura hasta que se active `stop_event` o se caigan todas las capturas.

        Al salir detiene las capturas, entrega al motor lo que quedó en la cola y lo cierra
        (`stop` emite los finales de las frases abiertas).
        """
        captures = [
            self._capture_factory(source, device, self._put)
            for source, device in self._devices.items()
        ]
        try:
            for capture in captures:
                capture.start()
            while not stop_event.is_set():
                try:
                    source, samples = self._queue.get(timeout=QUEUE_POLL_S)
                except queue.Empty:
                    if stop_event.is_set():
                        break
                    if not any(capture.is_alive for capture in captures):
                        logger.error("Todas las capturas se detuvieron")
                        break
                    continue
                self._engine.feed(source, samples)
        finally:
            for capture in captures:
                capture.stop()
            self._drain()
            self._engine.stop()

    def _put(self, source: str, samples: np.ndarray) -> None:
        self._queue.put((source, samples))

    def _drain(self) -> None:
        while True:
            try:
                source, samples = self._queue.get_nowait()
            except queue.Empty:
                return
            self._engine.feed(source, samples)
