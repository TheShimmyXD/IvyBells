"""
Máquina de estados de la escucha en vivo de la ventana (sin Qt).

Transiciones:
    stopped | error -> start    -> loading
    loading         -> loaded   -> listening
    loading | listening -> stop -> stopping
    stopping        -> finished -> stopped
    listening       -> finished -> error   (la captura se cayó sin pedirlo)
    loading         -> finished -> stopped (se detuvo mientras cargaba)
    cualquiera      -> fail     -> error
"""

from __future__ import annotations

from enum import StrEnum


class LiveState(StrEnum):
    STOPPED = "stopped"  # sin modelo ni captura
    LOADING = "loading"  # cargando el modelo en la GPU
    LISTENING = "listening"  # capturando y transcribiendo
    STOPPING = "stopping"  # cerrando las frases abiertas y liberando el modelo
    ERROR = "error"  # se detuvo por una falla; el motivo va en `message`


CAPTURE_LOST = "La captura de audio se detuvo"


class LiveLogic:
    def __init__(self) -> None:
        self.state = LiveState.STOPPED
        self.message = ""
        self.model = ""

    @property
    def is_busy(self) -> bool:
        return self.state in (LiveState.LOADING, LiveState.LISTENING, LiveState.STOPPING)

    @property
    def can_start(self) -> bool:
        return self.state in (LiveState.STOPPED, LiveState.ERROR)

    @property
    def can_stop(self) -> bool:
        return self.state in (LiveState.LOADING, LiveState.LISTENING)

    @property
    def status(self) -> str:
        """Texto corto para la línea de estado."""
        if self.state is LiveState.LOADING:
            return f"Cargando {self.model} en la GPU..."
        if self.state is LiveState.LISTENING:
            return "Escuchando"
        if self.state is LiveState.STOPPING:
            return "Deteniendo..."
        if self.state is LiveState.ERROR:
            return f"Error: {self.message}"
        return "Detenido"

    def start(self, model: str) -> dict:
        if not self.can_start:
            return self._payload(False, "Ya hay una escucha en curso")
        self.state = LiveState.LOADING
        self.model = model
        self.message = ""
        return self._payload(True)

    def loaded(self) -> dict:
        if self.state is not LiveState.LOADING:
            return self._payload(False, "No se estaba cargando un modelo")
        self.state = LiveState.LISTENING
        return self._payload(True)

    def stop(self) -> dict:
        if not self.can_stop:
            return self._payload(False, "No hay una escucha que detener")
        self.state = LiveState.STOPPING
        return self._payload(True)

    def finished(self) -> dict:
        if self.state is LiveState.LISTENING:
            return self.fail(CAPTURE_LOST)
        if self.state in (LiveState.LOADING, LiveState.STOPPING):
            self.state = LiveState.STOPPED
        return self._payload(True)

    def fail(self, message: str) -> dict:
        self.state = LiveState.ERROR
        self.message = message
        return self._payload(True, message)

    def _payload(self, ok: bool, message: str = "") -> dict:
        return {"ok": ok, "state": self.state, "status": self.status, "message": message}
