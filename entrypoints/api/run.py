"""
API local de IvyBells (``main.py --api``) sobre ``jacck_common.webapi``.

Por ahora solo ``GET /api/health``, para que la ventana minima de Tauri pruebe el crate
comun: token, puerto anunciado y apagado al cerrarse la entrada estandar. Las rutas de la
escucha, el Agente y la configuracion llegan despues.
"""

from __future__ import annotations

import logging
import tomllib

from fastapi import FastAPI
from jacck_common.webapi.names import SidecarNames
from jacck_common.webapi.serve import serve, session_token
from jacck_common.webapi.server import create_base_api

from paths import API_SESSION_JSON, ROOT

logger = logging.getLogger(__name__)

NAMES = SidecarNames("IVYBELLS")


def app_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def create_api(token: str) -> FastAPI:
    version = app_version()
    return create_base_api(title="IvyBells", token=token, health=lambda: {"version": version})


def run_api() -> int:
    """Corre la API hasta que la ventana la cierre (o Ctrl+C)."""
    token = session_token(NAMES)
    return serve(create_api(token), names=NAMES, token=token, session_path=API_SESSION_JSON)
