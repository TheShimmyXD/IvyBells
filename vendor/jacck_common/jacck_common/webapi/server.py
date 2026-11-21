"""
Base FastAPI de una API local (de Venona).

``create_base_api`` arma la app con su guardia (Host local, Origin permitido y token) y
``GET /api/health``; cada proyecto le agrega sus rutas. Ordenes por HTTP con JSON; el
avance por SSE (``sse_response``): ``id:`` es el numero del evento y con ``Last-Event-ID``
se retoma donde se corto; el canal se cierra tras su ultimo evento.

``jobs_router`` da las rutas del corredor de trabajos (``jobs.py``):
``POST /api/jobs/{kind}`` (409 si ya corre uno), ``GET /api/jobs?kind=`` (el ultimo de ese
tipo), ``GET /api/jobs/{id}``, ``POST /api/jobs/{id}/cancel`` y
``GET /api/jobs/{id}/events``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
from functools import partial

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jacck_common.webapi.events import Event
from jacck_common.webapi.jobs import JobBusyError, JobRunner, UnknownJobError
from jacck_common.webapi.security import (
    ALLOWED_HOSTS,
    ALLOWED_ORIGINS,
    BAD_ORIGIN_MESSAGE,
    NO_TOKEN_MESSAGE,
    origin_allowed,
    token_matches,
)

logger = logging.getLogger(__name__)

# Cada cuanto el canal manda un comentario si no hay eventos: asi nota que la interfaz se
# fue y suelta el hilo.
KEEPALIVE_SECONDS = 10.0
# Cada cuanto un canal mira si la API se esta apagando (``stop_streams``): la espera de
# eventos va en tramos de este largo, asi el apagado no queda colgado de un SSE abierto.
STOP_POLL_SECONDS = 0.25
NO_JOB_MESSAGE = "No hay un trabajo con ese id."

# (after, timeout) -> (eventos, cerrado): ``EventChannel.events_after`` o el de un trabajo.
EventsAfter = Callable[[int, float], tuple[list[Event], bool]]


def create_base_api(
    *,
    title: str,
    token: str,
    allowed_origins: tuple[str, ...] = ALLOWED_ORIGINS,
    is_public: Callable[[str, str], bool] | None = None,
    health: Callable[[], dict] | None = None,
) -> FastAPI:
    """App con el guardia y ``/api/health``. ``is_public(method, path)`` deja pasar sin
    token lo que no lo puede mandar (las fuentes de un iframe, por ejemplo)."""
    if not token:
        raise ValueError("La API no arranca sin token.")
    api = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)

    @api.middleware("http")
    async def guard(request: Request, call_next):
        if is_public is not None and is_public(request.method, request.url.path):
            return await call_next(request)
        if not origin_allowed(request.headers.get("origin"), allowed_origins):
            return JSONResponse({"detail": BAD_ORIGIN_MESSAGE}, status_code=403)
        if not token_matches(request.headers.get("authorization"), token):
            return JSONResponse({"detail": NO_TOKEN_MESSAGE}, status_code=401)
        return await call_next(request)

    # Fuera del guardia: la consulta previa (OPTIONS) del navegador no lleva token y la
    # respuesta 401/403 necesita sus cabeceras CORS para que la interfaz la lea.
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ALLOWED_HOSTS))

    @api.get("/api/health")
    def api_health() -> dict:
        return {"ok": True, **(health() if health is not None else {})}

    return api


def streams_stop(api: FastAPI) -> threading.Event:
    """La bandera de apagado de los canales de ``api`` (se crea la primera vez)."""
    flag = getattr(api.state, "streams_stop", None)
    if flag is None:
        flag = threading.Event()
        api.state.streams_stop = flag
    return flag


def stop_streams(api: FastAPI) -> None:
    """Termina todos los SSE abiertos de ``api``: lo pide ``serve`` al empezar a apagar."""
    streams_stop(api).set()


def sse_frame(event: Event) -> str:
    """Un evento en formato SSE: numero, tipo y datos en una linea de JSON."""
    data = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.seq}\nevent: {event.kind}\ndata: {data}\n\n"


def last_event_id(request: Request) -> int:
    raw = request.headers.get("last-event-id", "0").strip()
    return int(raw) if raw.isdigit() else 0


def sse_response(
    events_after: EventsAfter, request: Request, keepalive: float = KEEPALIVE_SECONDS
) -> StreamingResponse:
    """Reparte los eventos desde ``Last-Event-ID`` hasta que el canal se cierre o la
    interfaz se vaya. La espera corre en el grupo de hilos y no frena a los demas."""
    after = last_event_id(request)
    stopping = streams_stop(request.app)
    wait = min(keepalive, STOP_POLL_SECONDS)

    async def stream() -> AsyncIterator[str]:
        seen = after
        quiet_since = time.monotonic()
        while not stopping.is_set():
            events, finished = await asyncio.to_thread(events_after, seen, wait)
            for event in events:
                seen = event.seq
                yield sse_frame(event)
            if finished:
                return
            if events:
                quiet_since = time.monotonic()
            elif time.monotonic() - quiet_since >= keepalive:
                quiet_since = time.monotonic()
                yield ": sigue\n\n"
            if await request.is_disconnected():
                logger.info("La interfaz dejo el canal %s", request.url.path)
                return

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


def jobs_router(runner: JobRunner, keepalive: float = KEEPALIVE_SECONDS) -> APIRouter:
    router = APIRouter()

    @router.post("/api/jobs/{kind}")
    async def start_job(kind: str, request: Request) -> dict:
        body = await request.body()
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = None
        if not isinstance(params, dict):
            raise HTTPException(422, "Los parámetros van en un objeto JSON.")
        try:
            return runner.start(kind, params)
        except UnknownJobError:
            raise HTTPException(404, f"No hay trabajo «{kind}».") from None
        except JobBusyError:
            raise HTTPException(409, f"Ya corre un trabajo «{kind}».") from None

    @router.get("/api/jobs")
    def latest_job(kind: str) -> dict:
        # Con el 409 de un trabajo que ya corre, la web toma aqui su id y sigue su canal.
        if kind not in runner.kinds():
            raise HTTPException(404, f"No hay trabajo «{kind}».")
        return {"job": runner.latest(kind)}

    @router.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict:
        try:
            return runner.snapshot(job_id)
        except UnknownJobError:
            raise HTTPException(404, NO_JOB_MESSAGE) from None

    @router.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        try:
            return runner.cancel(job_id)
        except UnknownJobError:
            raise HTTPException(404, NO_JOB_MESSAGE) from None

    @router.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str, request: Request) -> StreamingResponse:
        try:
            runner.snapshot(job_id)
        except UnknownJobError:
            raise HTTPException(404, NO_JOB_MESSAGE) from None
        return sse_response(partial(runner.events_after, job_id), request, keepalive)

    return router
