"""
Adaptador Qt de la escucha en vivo (`app.live.LiveListening`).

La ventana solo habla con él: pide iniciar, detener y guardar, y escucha sus señales. La
orquestación vive en `app/`; aquí solo se pasan los avisos del hilo de la escucha al hilo
de la ventana y se convierten en señales.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.live import LiveListeners, LiveListening
from app.wiring import build_live
from domain.transcription.live_state import LiveLogic
from domain.transcription.live_view import LIVE_MODELS, LiveTranscript

# (clave para el motor, nombre en el botón, ayuda)
MODELS = LIVE_MODELS


class LiveCoordinator(QObject):
    """
    Signals
    -------
    state_changed(dict)          -> payload de la máquina de estados (`state`, `status`, ...).
    transcript_changed(str)      -> la fuente cuyo texto cambió.
    latency_changed(float, float) -> última latencia final y mediana.
    session_started()            -> primera escucha de la apertura (texto vacío); las
                                    siguientes se reanudan sin borrar nada.
    sources_changed()            -> se abrió o cerró un canal (`closed_sources`).
    """

    state_changed = Signal(dict)
    transcript_changed = Signal(str)
    latency_changed = Signal(float, float)
    session_started = Signal()
    sources_changed = Signal()
    # Tarea que llega del hilo de la escucha: Qt la pone en cola y la corre en este hilo.
    _posted = Signal(object)

    def __init__(self, listening: LiveListening | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.listening = listening if listening is not None else build_live()
        self._posted.connect(self._run_posted)
        self.listening.attach(
            self._posted.emit,
            LiveListeners(
                state=self.state_changed.emit,
                transcript=self.transcript_changed.emit,
                latency=self.latency_changed.emit,
                session_started=self.session_started.emit,
                sources=self.sources_changed.emit,
            ),
        )

    # -- Lo que leen la ventana, el Agente y el chat ---------------

    @property
    def logic(self) -> LiveLogic:
        return self.listening.logic

    @property
    def transcript(self) -> LiveTranscript:
        return self.listening.transcript

    @property
    def closed_sources(self) -> set[str]:
        return self.listening.closed_sources

    @property
    def last_path(self) -> Path | None:
        """El `.md` de esta apertura, o None si todavía no se inició ninguna escucha."""
        return self.listening.last_path

    # -- Pedidos de la ventana ---------------------------------

    def is_open(self, source: str) -> bool:
        return self.listening.is_open(source)

    def set_source_open(self, source: str, is_open: bool) -> bool:
        return self.listening.set_source_open(source, is_open)

    def read_sources(self):
        """Fuentes de PipeWire por tipo y las elegidas por defecto (`SourceChoices`)."""
        return self.listening.read_sources()

    def start(self, model: str, devices: dict[str, str]) -> None:
        self.listening.start(model, devices)

    def stop(self) -> None:
        self.listening.stop()

    def save_copy(self, target: Path) -> bool:
        return self.listening.save_copy(target)

    def close(self) -> None:
        """Detiene la escucha y espera a su hilo; la ventana lo llama al cerrarse."""
        self.listening.close()

    # -- Internos ----------------------------------------------

    @Slot(object)
    def _run_posted(self, task: Callable[[], None]) -> None:
        task()
