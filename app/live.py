"""
Escucha en vivo sin Qt: carga el modelo, captura, transcribe y escribe el `.md`.

`LiveListening` es el caso de uso que piden las puertas (la ventana Qt y, desde FW.4, la
API): guarda el estado, el texto de cada columna y los canales, y corre cada escucha en su
propio hilo (`ListeningRun`). Lo que sale de ese hilo se entrega con `post` al hilo dueño,
así que el estado solo cambia en un hilo y ninguna puerta orquesta la escucha por su cuenta.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from domain.transcription.engine import EventCallback, TranscriptEvent, TranscriptionEngine
from domain.transcription.live_state import LiveLogic
from domain.transcription.live_view import SOURCES, LatencyTracker, LiveTranscript
from domain.transcription.transcript_markdown import format_latency_footer, format_latency_line
from services.service_capture import AudioCapture, BlockCallback
from services.service_live import CaptureFactory, LiveSession
from services.service_transcript import TranscriptWriter

logger = logging.getLogger(__name__)

EngineFactory = Callable[[EventCallback, str, str], TranscriptionEngine]
# Entrega una tarea al hilo dueño (Qt: una señal en cola; asyncio: call_soon_threadsafe).
Post = Callable[[Callable[[], None]], None]

DEFAULT_MODEL = "large-v3-turbo"
COMPUTE_TYPE = "int8"
# Al cerrar, la escucha cierra las frases abiertas (una llamada al modelo cada una).
CLOSE_TIMEOUT_S = 20.0


def call_now(task: Callable[[], None]) -> None:
    """`Post` sin hilo dueño: corre la tarea en el hilo que avisa (pruebas y consola)."""
    task()


def _ignore(*_args: object) -> None:
    pass


@dataclass
class LiveListeners:
    """
    Avisos de `LiveListening` a su dueño, siempre en el hilo dueño. Por defecto no hacen nada.

    state(dict)                -> payload de la máquina de estados (`state`, `status`, ...).
    transcript(str)            -> la fuente cuyo texto cambió.
    latency(float, float)      -> última latencia final y mediana.
    session_started()          -> primera escucha de la apertura (texto vacío); las
                                  siguientes se reanudan sin borrar nada.
    sources()                  -> se abrió o cerró un canal (`closed_sources`).
    event(TranscriptEvent)     -> el texto provisional o final tal como llegó (la consola
                                  lo imprime; la ventana lee `transcript`).
    """

    state: Callable[[dict], None] = _ignore
    transcript: Callable[[str], None] = _ignore
    latency: Callable[[float, float], None] = _ignore
    session_started: Callable[[], None] = _ignore
    sources: Callable[[], None] = _ignore
    event: Callable[[TranscriptEvent], None] = _ignore


@dataclass(frozen=True)
class RunCallbacks:
    """
    Avisos de una corrida, en el hilo de la escucha.

    loaded(datetime, bool) -> modelo listo; hora de inicio del tramo y si es el primero
                              del `.md` (los siguientes se reanudan en el mismo).
    event(TranscriptEvent) -> texto provisional o final de una fuente.
    latency(float, float)  -> última latencia final y su mediana, en segundos.
    failed(str)            -> motivo de la falla, en una línea.
    finished(dict)         -> siempre al final: `_request_id`, `path` (o None) y `phrases`
                              (las de toda la apertura).
    """

    loaded: Callable[[datetime, bool], None] = _ignore
    event: Callable[[TranscriptEvent], None] = _ignore
    latency: Callable[[float, float], None] = _ignore
    failed: Callable[[str], None] = _ignore
    finished: Callable[[dict], None] = _ignore


class ListeningRun:
    """Una escucha, de Iniciar a Detener: corre entera en el hilo que llama a `run()`."""

    def __init__(
        self,
        *,
        engine_factory: EngineFactory,
        model: str,
        compute_type: str,
        devices: dict[str, str],
        writer: TranscriptWriter,
        stop_event: threading.Event,
        request_id: int,
        callbacks: RunCallbacks,
        capture_factory: CaptureFactory = AudioCapture,
        closed: Iterable[str] = (),
    ) -> None:
        self._engine_factory = engine_factory
        self._model = model
        self._compute_type = compute_type
        self._devices = devices
        self._writer = writer
        self._stop_event = stop_event
        self._request_id = request_id
        self._callbacks = callbacks
        self._capture_factory = capture_factory
        self._tracker = LatencyTracker()
        # Los canales cerrados se piden desde el hilo dueño: antes de que exista la
        # sesión se guardan aquí, y después se le pasan a ella.
        self._lock = threading.Lock()
        self._closed = set(closed)
        self._session: LiveSession | None = None

    def set_source_open(self, source: str, is_open: bool) -> None:
        """Abre o cierra un canal; se puede llamar desde cualquier hilo."""
        with self._lock:
            if is_open:
                self._closed.discard(source)
            else:
                self._closed.add(source)
            if self._session is not None:
                self._session.set_source_open(source, is_open)

    def run(self) -> None:
        writer = self._writer
        callbacks = self._callbacks
        began = False
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
            is_new = writer.begin(started, f"{self._model} {self._compute_type}", self._devices)
            began = True
            handlers += [writer.add, self._on_event]
            callbacks.loaded(started, is_new)
            with self._lock:
                session = self._session = LiveSession(
                    engine, self._devices, self._timed_capture, closed=self._closed
                )
            session.run(self._stop_event)
        except Exception as exc:
            # Frontera del hilo: sin esto el dueño se queda esperando para siempre.
            logger.exception("La escucha en vivo falló")
            callbacks.failed(str(exc) or type(exc).__name__)
        finally:
            if began:
                writer.end_segment(self._latency_footer())
            callbacks.finished(
                {"_request_id": self._request_id, "path": writer.path, "phrases": writer.phrases}
            )

    def _on_event(self, event: TranscriptEvent) -> None:
        if event.is_final:
            value = self._tracker.add_final(event.end_s, time.monotonic(), event.source)
            if value is not None:
                self._callbacks.latency(value, self._tracker.median)
        self._callbacks.event(event)

    def _latency_footer(self) -> str:
        """Deja en el log la latencia de cada canal y devuelve el pie del .md."""
        summaries = self._tracker.summary()
        if summaries:
            lines = [format_latency_line(source, item) for source, item in summaries.items()]
            logger.info("Latencia final del tramo: %s", "; ".join(lines))
        return format_latency_footer(summaries)

    def _timed_capture(self, source: str, device: str, on_block: BlockCallback) -> AudioCapture:
        """La captura de siempre, marcando cuándo llegó el primer bloque (origen de la latencia)."""

        def on_timed_block(block_source: str, samples: np.ndarray) -> None:
            self._tracker.mark_audio(len(samples), time.monotonic())
            on_block(block_source, samples)

        return self._capture_factory(source, device, on_timed_block)


class LiveListening:
    """
    Caso de uso de la escucha: iniciar, detener, canales, guardar copia y el texto en vivo.

    Se usa desde un solo hilo (el dueño); los avisos llegan a `listeners` en ese hilo.
    """

    def __init__(
        self,
        engine_factory: EngineFactory,
        transcripts_dir: Path,
        closed_sources: Iterable[str] = (),
        *,
        capture_factory: CaptureFactory = AudioCapture,
    ) -> None:
        self._engine_factory = engine_factory
        self._capture_factory = capture_factory
        self.logic = LiveLogic()
        self.transcript = LiveTranscript()
        # Un solo .md por apertura de la app; se crea en el primer Iniciar.
        self.writer = TranscriptWriter(transcripts_dir)
        self.listeners = LiveListeners()
        self._post: Post = call_now
        self._request_id = 0
        self._stop_event = threading.Event()
        self._run: ListeningRun | None = None
        self._thread: threading.Thread | None = None
        # Canales cerrados: se capturan pero no llegan al motor. Siempre queda uno abierto.
        self.closed_sources: set[str] = set()
        for source in closed_sources:
            self.set_source_open(source, False)

    def attach(self, post: Post, listeners: LiveListeners) -> None:
        """Fija el hilo dueño y quién recibe los avisos; la puerta lo llama una vez al armarse."""
        self._post = post
        self.listeners = listeners

    # -- Pedidos del dueño ---------------------------------------

    def is_open(self, source: str) -> bool:
        return source not in self.closed_sources

    def set_source_open(self, source: str, is_open: bool) -> bool:
        """
        Abre o cierra un canal, también con la escucha en marcha. Devuelve False si no
        cambia nada o si se pide cerrar el único canal abierto.
        """
        if source not in SOURCES or self.is_open(source) == is_open:
            return False
        if not is_open and len(self.closed_sources) + 1 >= len(SOURCES):
            return False
        if is_open:
            self.closed_sources.discard(source)
        else:
            self.closed_sources.add(source)
        if self._run is not None:
            self._run.set_source_open(source, is_open)
        self.listeners.sources()
        return True

    def read_sources(self):
        """Fuentes de PipeWire por tipo y las elegidas por defecto (`SourceChoices`)."""
        from services.service_pipewire import read_source_choices

        return read_source_choices()

    def default_devices(self) -> dict[str, str]:
        """Las fuentes que PipeWire da por defecto: el monitor de la salida y el micrófono."""
        capture = self.read_sources().selected
        devices = {}
        if capture.monitor:
            devices["ellos"] = capture.monitor.name
        if capture.microphone:
            devices["tu"] = capture.microphone.name
        return devices

    def start(self, model: str, devices: dict[str, str], compute_type: str = COMPUTE_TYPE) -> None:
        if self._thread is not None and self._thread.is_alive():
            logger.warning("La escucha anterior aún se está cerrando")
            return
        if not devices:
            self.listeners.state(self.logic.fail("No hay ninguna fuente de audio elegida"))
            return
        payload = self.logic.start(model)
        if payload["ok"]:
            self._launch(model, devices, compute_type)
        self.listeners.state(payload)

    def stop(self) -> None:
        payload = self.logic.stop()
        if payload["ok"]:
            self._stop_event.set()
        self.listeners.state(payload)

    @property
    def last_path(self) -> Path | None:
        """El `.md` de esta apertura, o None si todavía no se inició ninguna escucha."""
        return self.writer.path

    def save_copy(self, target: Path) -> bool:
        """Copia a `target` todo lo transcrito desde que se abrió la app, aunque siga escuchando."""
        try:
            self.writer.copy_to(target)
        except OSError as exc:
            logger.error("No se pudo copiar la transcripción a %s: %s", target, exc)
            return False
        logger.info("Transcripción copiada a %s", target)
        return True

    def wait(self, timeout_s: float | None = None) -> bool:
        """Espera a que termine el hilo de la escucha; True si ya no queda ninguno corriendo."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout_s)
        return not thread.is_alive()

    def close(self, timeout_s: float = CLOSE_TIMEOUT_S) -> None:
        """Detiene la escucha y espera a su hilo; la puerta lo llama al cerrarse."""
        self._stop_event.set()
        if not self.wait(timeout_s):
            logger.warning("La escucha no terminó en %.0f s; se cierra igual", timeout_s)
        self.writer.close()

    # -- Avisos de la corrida (ya en el hilo dueño) ---------------

    def on_loaded(self, started: datetime, is_new: bool = True) -> None:
        if is_new:
            self.transcript.reset(started)
            self.listeners.session_started()
        else:
            self.transcript.resume(started)
        for source in SOURCES:
            self.listeners.transcript(source)
        self.listeners.state(self.logic.loaded())

    def on_event(self, event: TranscriptEvent) -> None:
        self.transcript.apply(event)
        self.listeners.transcript(event.source)
        self.listeners.event(event)

    def on_latency(self, last: float, median: float) -> None:
        self.listeners.latency(last, median)

    def on_failed(self, message: str) -> None:
        self.listeners.state(self.logic.fail(message))

    def on_finished(self, payload: dict) -> None:
        if payload.get("_request_id") != self._request_id:
            return
        self._run = None
        if payload.get("path") is not None:
            logger.info("%d frases guardadas en %s", payload["phrases"], payload["path"])
        self.listeners.state(self.logic.finished())

    # -- Internos ------------------------------------------------

    def _posting(self, handler: Callable[..., None]) -> Callable[..., None]:
        """Envuelve `handler` para que corra en el hilo dueño con los mismos argumentos."""
        post = self._post
        return lambda *args: post(lambda: handler(*args))

    def _launch(self, model: str, devices: dict[str, str], compute_type: str) -> None:
        self._request_id += 1
        self._stop_event = threading.Event()
        callbacks = RunCallbacks(
            loaded=self._posting(self.on_loaded),
            event=self._posting(self.on_event),
            latency=self._posting(self.on_latency),
            failed=self._posting(self.on_failed),
            finished=self._posting(self.on_finished),
        )
        run = self._run = ListeningRun(
            engine_factory=self._engine_factory,
            model=model,
            compute_type=compute_type,
            devices=devices,
            writer=self.writer,
            stop_event=self._stop_event,
            request_id=self._request_id,
            callbacks=callbacks,
            capture_factory=self._capture_factory,
            closed=self.closed_sources,
        )
        # daemon: si la GPU se cuelga, cerrar la app no espera más que CLOSE_TIMEOUT_S.
        self._thread = threading.Thread(target=run.run, name="ivybells-live", daemon=True)
        self._thread.start()
