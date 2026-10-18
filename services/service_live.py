"""
Sesión en vivo: las capturas de cada fuente ponen bloques en una cola y un solo hilo
(el que llama a `run`) los entrega al motor, en el orden en que llegaron.

Un canal cerrado sigue capturando (reabrir es instantáneo y no toca PipeWire), pero sus
bloques no llegan al motor: solo se cuentan para que sus tiempos sigan al reloj.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable, Iterable

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
        closed: Iterable[str] = (),
    ) -> None:
        self._engine = engine
        self._devices = devices
        self._capture_factory = capture_factory
        # En la cola van bloques de audio y, como bool, las órdenes de abrir o cerrar un canal.
        self._queue: queue.Queue[tuple[str, np.ndarray | bool]] = queue.Queue()
        self._closed = set(closed)
        self._skipped: dict[str, int] = {}

    def set_source_open(self, source: str, is_open: bool) -> None:
        """Abre o cierra un canal desde otro hilo; se aplica en orden con sus bloques."""
        self._queue.put((source, is_open))

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
                    source, item = self._queue.get(timeout=QUEUE_POLL_S)
                except queue.Empty:
                    if stop_event.is_set():
                        break
                    if not any(capture.is_alive for capture in captures):
                        logger.error("Todas las capturas se detuvieron")
                        break
                    continue
                self._handle(source, item)
        finally:
            for capture in captures:
                capture.stop()
            self._drain()
            self._engine.stop()

    def _put(self, source: str, samples: np.ndarray) -> None:
        self._queue.put((source, samples))

    def _handle(self, source: str, item: np.ndarray | bool) -> None:
        if isinstance(item, bool):
            self._apply_open(source, item)
        elif source in self._closed:
            self._skipped[source] = self._skipped.get(source, 0) + len(item)
        else:
            skipped = self._skipped.pop(source, 0)
            if skipped:
                self._engine.skip(source, skipped)
            self._engine.feed(source, item)

    def _apply_open(self, source: str, is_open: bool) -> None:
        if is_open:
            self._closed.discard(source)
        elif source not in self._closed:
            self._closed.add(source)
            self._engine.end_source(source)

    def _drain(self) -> None:
        while True:
            try:
                source, item = self._queue.get_nowait()
            except queue.Empty:
                return
            self._handle(source, item)
