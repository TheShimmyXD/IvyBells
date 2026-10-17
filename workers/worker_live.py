"""
Worker de la escucha en vivo: carga el modelo, captura y transcribe hasta que se pida parar.

Corre en su propio QThread; la UI solo recibe señales y nunca espera a la GPU.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from core.engine import EventCallback, TranscriptEvent, TranscriptionEngine
from core.live_view import LatencyTracker
from services.service_capture import AudioCapture, BlockCallback
from services.service_live import CaptureFactory, LiveSession
from services.service_transcript import TranscriptWriter

logger = logging.getLogger(__name__)

EngineFactory = Callable[[EventCallback, str, str], TranscriptionEngine]


class LiveWorker(QObject):
    """
    Signals
    -------
    loaded(datetime)       -> modelo listo; hora de inicio del `.md`.
    event(TranscriptEvent) -> texto provisional o final de una fuente.
    latency(float, float)  -> última latencia final y su mediana, en segundos.
    failed(str)            -> motivo de la falla, en una línea.
    finished(dict)         -> siempre al final: `_request_id`, `path` (o None) y `phrases`.
    """

    loaded = Signal(object)
    event = Signal(object)
    latency = Signal(float, float)
    failed = Signal(str)
    finished = Signal(dict)

    def __init__(
        self,
        *,
        engine_factory: EngineFactory,
        model: str,
        compute_type: str,
        devices: dict[str, str],
        transcripts_dir: Path,
        stop_event: threading.Event,
        request_id: int,
        capture_factory: CaptureFactory = AudioCapture,
    ) -> None:
        super().__init__()
        self._engine_factory = engine_factory
        self._model = model
        self._compute_type = compute_type
        self._devices = devices
        self._transcripts_dir = transcripts_dir
        self._stop_event = stop_event
        self._request_id = request_id
        self._capture_factory = capture_factory
        self._tracker = LatencyTracker()

    def run(self) -> None:
        writer: TranscriptWriter | None = None
        try:
            handlers: list[EventCallback] = []

            def dispatch(event: TranscriptEvent) -> None:
                for handler in handlers:
                    handler(event)

            engine = self._engine_factory(dispatch, self._model, self._compute_type)
            logger.info("Cargando %s %s en la GPU...", self._model, self._compute_type)
            engine.start()
            if self._stop_event.is_set():
                return
            started = datetime.now()
            writer = TranscriptWriter(
                self._transcripts_dir, started, f"{self._model} {self._compute_type}", self._devices
            )
            handlers += [writer.add, self._emit_event]
            self.loaded.emit(started)
            LiveSession(engine, self._devices, self._timed_capture).run(self._stop_event)
        except Exception as exc:
            # Frontera del hilo: sin esto la UI se queda esperando para siempre.
            logger.exception("La escucha en vivo falló")
            self.failed.emit(str(exc) or type(exc).__name__)
        finally:
            if writer is not None:
                writer.close()
            self.finished.emit(
                {
                    "_request_id": self._request_id,
                    "path": writer.path if writer else None,
                    "phrases": writer.phrases if writer else 0,
                }
            )

    def _emit_event(self, event: TranscriptEvent) -> None:
        if event.is_final:
            value = self._tracker.add_final(event.end_s, time.monotonic())
            if value is not None:
                self.latency.emit(value, self._tracker.median)
        self.event.emit(event)

    def _timed_capture(self, source: str, device: str, on_block: BlockCallback) -> AudioCapture:
        """La captura de siempre, marcando cuándo llegó el primer bloque (origen de la latencia)."""

        def on_timed_block(block_source: str, samples: np.ndarray) -> None:
            self._tracker.mark_audio(len(samples), time.monotonic())
            on_block(block_source, samples)

        return self._capture_factory(source, device, on_timed_block)
