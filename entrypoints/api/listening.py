"""
Rutas de la escucha en vivo y su canal de eventos.

`LiveListening` entrega sus avisos en el bucle de asyncio (`owner.LoopOwner`) y aquí se
vuelven eventos de un `EventChannel` por apertura, que el SSE reparte a cualquier número
de lectores; `fan_out` los pasa además al Agente. Las rutas que tocan la escucha son
`async`: corren en ese mismo bucle, el hilo dueño.

Eventos: `state` (carga de la máquina de estados), `phrase` (provisional o final de un
canal), `latency` (última y mediana, en segundos), `session` (primera escucha de la
apertura), `sources` (canales cerrados) y `saved` (copia del `.md`).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import fields
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from jacck_common.webapi.events import EventChannel
from jacck_common.webapi.server import KEEPALIVE_SECONDS, sse_response
from pydantic import BaseModel

from app.live import COMPUTE_TYPE, DEFAULT_MODEL, LiveListeners, LiveListening
from domain.transcription.engine import TranscriptEvent
from domain.transcription.live_view import SOURCES, Line
from entrypoints.api.owner import LoopOwner

logger = logging.getLogger(__name__)

NO_TRANSCRIPT_MESSAGE = "Todavía no hay transcripción que guardar."


class StartRequest(BaseModel):
    model: str = DEFAULT_MODEL
    compute_type: str = COMPUTE_TYPE
    # Fuente -> dispositivo de PipeWire; sin ellas, las que PipeWire da por defecto.
    devices: dict[str, str] | None = None


class SourceRequest(BaseModel):
    open: bool


class SaveRequest(BaseModel):
    path: str


def state_data(payload: dict) -> dict:
    return {key: payload.get(key) for key in ("ok", "state", "status", "message")}


def line_data(line: Line | None) -> dict | None:
    return None if line is None else {"clock": line.clock, "text": line.text}


def phrase_data(event: TranscriptEvent, clock: str) -> dict:
    return {
        "source": event.source,
        "final": event.is_final,
        "clock": clock,
        "text": event.text.strip(),
        "stable_words": event.stable_words,
    }


def _seconds(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def fan_out(*groups: LiveListeners) -> LiveListeners:
    """Un `LiveListeners` que pasa cada aviso a todos los grupos, en orden."""

    def each(name: str):
        handlers = [getattr(group, name) for group in groups]

        def call(*args: object) -> None:
            for handler in handlers:
                handler(*args)

        return call

    return LiveListeners(**{field.name: each(field.name) for field in fields(LiveListeners)})


def channel_listeners(listening: LiveListening, channel: EventChannel) -> LiveListeners:
    """Los avisos de la escucha, vueltos eventos del canal (ya en el bucle)."""

    def on_event(event: TranscriptEvent) -> None:
        clock = listening.transcript.clock(event.start_s)
        channel.emit("phrase", phrase_data(event, clock))

    return LiveListeners(
        state=lambda payload: channel.emit("state", state_data(payload)),
        latency=lambda last, median: channel.emit(
            "latency", {"last_s": _seconds(last), "median_s": _seconds(median)}
        ),
        session_started=lambda: channel.emit("session", {"new": True}),
        sources=lambda: channel.emit("sources", {"closed": sorted(listening.closed_sources)}),
        event=on_event,
    )


def snapshot(listening: LiveListening, channel: EventChannel) -> dict:
    """Todo lo que la interfaz necesita al abrirse; `last_event` es su `Last-Event-ID`."""
    logic = listening.logic
    transcript = listening.transcript
    count, _, _ = channel.state()
    path = listening.last_path
    return {
        "state": logic.state,
        "status": logic.status,
        "message": logic.message,
        "model": logic.model,
        "closed_sources": sorted(listening.closed_sources),
        "path": None if path is None else str(path),
        "transcript": {
            source: {
                "finals": [line_data(line) for line in transcript.finals(source)],
                "partial": line_data(transcript.partial(source)),
            }
            for source in SOURCES
        },
        "last_event": count,
    }


def _last_state(channel: EventChannel) -> dict:
    """La carga que la escucha acaba de emitir: ninguna otra tarea corre en el bucle entre medio."""
    _, last, _ = channel.state()
    return dict(last.data) if last is not None and last.kind == "state" else {}


def listening_router(
    listening: LiveListening,
    owner: LoopOwner,
    keepalive: float = KEEPALIVE_SECONDS,
    followers: LiveListeners | None = None,
) -> tuple[APIRouter, EventChannel]:
    """
    Rutas de la escucha y el canal de esta apertura (una sola `LiveListening` por proceso).
    `followers` recibe los mismos avisos después del canal (el Agente).
    """
    router = APIRouter()
    channel = EventChannel()
    listeners = channel_listeners(listening, channel)
    if followers is not None:
        listeners = fan_out(listeners, followers)
    listening.attach(owner, listeners)

    @router.get("/api/listening")
    async def get_listening() -> dict:
        return snapshot(listening, channel)

    @router.post("/api/listening/start")
    async def start(body: StartRequest) -> dict:
        devices = body.devices
        if devices is None:
            # pactl es un proceso aparte: fuera del bucle.
            devices = await asyncio.to_thread(listening.default_devices)
        unknown = set(devices) - set(SOURCES)
        if unknown:
            raise HTTPException(422, f"Fuentes desconocidas: {', '.join(sorted(unknown))}.")
        listening.start(body.model, devices, body.compute_type)
        return _last_state(channel)

    @router.post("/api/listening/stop")
    async def stop() -> dict:
        listening.stop()
        return _last_state(channel)

    @router.post("/api/listening/sources/{source}")
    async def set_source(source: str, body: SourceRequest) -> dict:
        if source not in SOURCES:
            raise HTTPException(404, f"No hay canal «{source}».")
        changed = listening.set_source_open(source, body.open)
        return {"changed": changed, "closed": sorted(listening.closed_sources)}

    @router.post("/api/listening/save")
    async def save(body: SaveRequest) -> dict:
        target = Path(body.path)
        if not target.is_absolute() or target.suffix != ".md":
            raise HTTPException(422, "La copia va a una ruta absoluta terminada en .md.")
        if listening.last_path is None:
            raise HTTPException(409, NO_TRANSCRIPT_MESSAGE)
        if not listening.save_copy(target):
            raise HTTPException(500, "No se pudo copiar la transcripción.")
        channel.emit("saved", {"path": str(target)})
        return {"path": str(target)}

    @router.get("/api/listening/events")
    def events(request: Request) -> StreamingResponse:
        return sse_response(channel.events_after, request, keepalive)

    return router, channel
