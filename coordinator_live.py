"""
Coordinador de la escucha en vivo: une la máquina de estados, el worker y los servicios.

La ventana solo habla con él: pide iniciar, detener y guardar, y escucha sus señales.
"""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.engine import TranscriptEvent
from core.live_state import LiveLogic
from core.live_view import LiveTranscript
from paths import TRANSCRIPTS_DIR
from workers.worker_live import EngineFactory, LiveWorker
from workers.worker_runner import RequestSequence, start_worker, stop_thread

logger = logging.getLogger(__name__)

# (clave para el motor, nombre en el botón, ayuda)
MODELS = (
    ("small", "small", "El más rápido (mediana 0,5 s) pero erra más"),
    ("medium", "medium", "Intermedio (mediana 1,3 s)"),
    ("large-v3-turbo", "turbo", "El elegido: mediana 1,8 s y el mejor texto"),
)
DEFAULT_MODEL = "large-v3-turbo"
COMPUTE_TYPE = "int8"
# Al cerrar, el worker cierra las frases abiertas (una llamada al modelo cada una).
CLOSE_TIMEOUT_MS = 20_000


def _default_engine_factory(on_event, model, compute_type):
    # Import diferido: faster-whisper y CUDA solo se cargan al iniciar una escucha.
    from services.service_streaming import create_whisper_engine

    return create_whisper_engine(on_event, model, compute_type)


class LiveCoordinator(QObject):
    """
    Signals
    -------
    state_changed(dict)          -> payload de la máquina de estados (`state`, `status`, ...).
    transcript_changed(str)      -> la fuente cuyo texto cambió.
    latency_changed(float, float) -> última latencia final y mediana.
    """

    state_changed = Signal(dict)
    transcript_changed = Signal(str)
    latency_changed = Signal(float, float)

    def __init__(
        self,
        engine_factory: EngineFactory = _default_engine_factory,
        transcripts_dir: Path = TRANSCRIPTS_DIR,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine_factory = engine_factory
        self._transcripts_dir = transcripts_dir
        self.logic = LiveLogic()
        self.transcript = LiveTranscript()
        self.last_path: Path | None = None
        self._requests = RequestSequence()
        self._stop_event = threading.Event()
        self._worker: LiveWorker | None = None
        self._thread: QThread | None = None

    # -- Pedidos de la ventana ---------------------------------

    def read_sources(self):
        """Fuentes de PipeWire por tipo y las elegidas por defecto (`SourceChoices`)."""
        from services.service_pipewire import read_source_choices

        return read_source_choices()

    def start(self, model: str, devices: dict[str, str]) -> None:
        if self._thread is not None:
            logger.warning("La escucha anterior aún se está cerrando")
            return
        if not devices:
            self._emit_state(self.logic.fail("No hay ninguna fuente de audio elegida"))
            return
        payload = self.logic.start(model)
        if payload["ok"]:
            self._launch(model, devices)
        self._emit_state(payload)

    def stop(self) -> None:
        payload = self.logic.stop()
        if payload["ok"]:
            self._stop_event.set()
        self._emit_state(payload)

    def save_copy(self, target: Path) -> bool:
        """Copia el `.md` de la última escucha (se escribe frase a frase) a `target`."""
        if self.last_path is None or not self.last_path.exists():
            return False
        try:
            shutil.copyfile(self.last_path, target)
        except OSError as exc:
            logger.error("No se pudo copiar la transcripción a %s: %s", target, exc)
            return False
        logger.info("Transcripción copiada a %s", target)
        return True

    def close(self) -> None:
        """Detiene la escucha y espera al worker; la ventana lo llama al cerrarse."""
        self._stop_event.set()
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker (llegan en el hilo principal) ------

    @Slot(object)
    def on_loaded(self, started: datetime) -> None:
        self.transcript.reset(started)
        for source in ("ellos", "tu"):
            self.transcript_changed.emit(source)
        self._emit_state(self.logic.loaded())

    @Slot(object)
    def on_event(self, event: TranscriptEvent) -> None:
        self.transcript.apply(event)
        self.transcript_changed.emit(event.source)

    @Slot(float, float)
    def on_latency(self, last: float, median: float) -> None:
        self.latency_changed.emit(last, median)

    @Slot(str)
    def on_failed(self, message: str) -> None:
        self._emit_state(self.logic.fail(message))

    @Slot(dict)
    def on_finished(self, payload: dict) -> None:
        if not self._requests.is_current(payload):
            return
        if payload.get("path") is not None:
            self.last_path = payload["path"]
            logger.info("%d frases guardadas en %s", payload["phrases"], self.last_path)
        self._emit_state(self.logic.finished())

    # -- Internos ----------------------------------------------

    def _launch(self, model: str, devices: dict[str, str]) -> None:
        self._stop_event = threading.Event()
        worker = self._worker = LiveWorker(
            engine_factory=self._engine_factory,
            model=model,
            compute_type=COMPUTE_TYPE,
            devices=devices,
            transcripts_dir=self._transcripts_dir,
            stop_event=self._stop_event,
            request_id=self._requests.next(),
        )
        worker.loaded.connect(self.on_loaded)
        worker.event.connect(self.on_event)
        worker.latency.connect(self.on_latency)
        worker.failed.connect(self.on_failed)
        self._thread = start_worker(
            self, worker, on_done=self.on_finished, on_cleared=self._clear_refs
        )

    def _clear_refs(self) -> None:
        self._worker = None
        self._thread = None

    def _emit_state(self, payload: dict) -> None:
        self.state_changed.emit(payload)
