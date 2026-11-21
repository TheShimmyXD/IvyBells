"""
API local para una interfaz web en Tauri (sacada de Venona).

Necesita el extra ``webapi`` (FastAPI y uvicorn): ``pip install -e "../jacck_common[webapi]"``.

- ``names``: prefijo de la app y los nombres que comparte con el crate ``jacck_tauri``.
- ``security``: token, Host local y Origin permitido.
- ``events``: canal de eventos numerados para el SSE.
- ``jobs``: corredor de trabajos largos sin Qt.
- ``server``: base FastAPI con el guardia, SSE y rutas de trabajos.
- ``serve``: socket local con puerto al azar, archivo de sesion y apagado por la entrada
  estandar.
"""

from __future__ import annotations
