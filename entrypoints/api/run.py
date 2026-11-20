"""
API local de IvyBells (``main.py --api``) sobre ``jacck_common.webapi``.

``GET /api/health`` y la escucha en vivo (``listening.py``): token, Origin de la
ventana de Tauri o del Vite de ``web/``, puerto anunciado y apagado al cerrarse la entrada
estándar. El Agente, el chat y la configuración llegan despues (FW.4).
"""

from __future__ import annotations

import logging
import tomllib

from fastapi import FastAPI
from jacck_common.webapi.names import SidecarNames
from jacck_common.webapi.security import allowed_origins
from jacck_common.webapi.serve import serve, session_token
from jacck_common.webapi.server import KEEPALIVE_SECONDS, create_base_api

from app.live import LiveListening
from app.wiring import build_live
from entrypoints.api.listening import listening_router
from paths import API_SESSION_JSON, ROOT

logger = logging.getLogger(__name__)

NAMES = SidecarNames("IVYBELLS")
# El de web/vite.config.ts (5173 es el de Venona: se pueden tener las dos abiertas).
VITE_PORT = 5174


def app_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def create_api(
    token: str, listening: LiveListening, keepalive: float = KEEPALIVE_SECONDS
) -> FastAPI:
    version = app_version()
    api = create_base_api(
        title="IvyBells",
        token=token,
        allowed_origins=allowed_origins(VITE_PORT),
        health=lambda: {"version": version},
    )
    router, channel = listening_router(listening, keepalive)
    api.include_router(router)
    api.state.listening_channel = channel
    return api


def run_api() -> int:
    """Corre la API hasta que la ventana la cierre (o Ctrl+C); al final cierra la escucha."""
    token = session_token(NAMES)
    listening = build_live()
    try:
        return serve(
            create_api(token, listening), names=NAMES, token=token, session_path=API_SESSION_JSON
        )
    finally:
        listening.close()
