"""
Lo que la API recuerda en `app_settings.json`, como la ventana.

Las rutas de la escucha y del Agente guardan lo que el autor elige (modelo y dispositivos al
empezar, canales cerrados, interlocutor y modo); las preferencias de la vista (tema, módulo
y panel del Agente) las guarda la interfaz con `POST /api/prefs`. Nada de esto se guarda
cuando cambia solo (por ejemplo, el interlocutor que pasa al otro canal al cerrarse el suyo).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import AGENT_PANELS, MODULE_NAMES, THEME_NAMES, AppConfig

Remember = Callable[[str, object], object]

# Clave -> valores válidos; las demás claves de `app_settings.json` no se escriben por aquí.
VIEW_PREFS: dict[str, tuple[str, ...]] = {
    "theme": THEME_NAMES,
    "module": MODULE_NAMES,
    "agent_panel": AGENT_PANELS,
}
# Lo que lee la interfaz al abrirse.
SHOWN = ("theme", "module", "agent_panel", "live_model", "devices", "speaker", "agent_mode")


class PrefRequest(BaseModel):
    key: str
    value: str


class Prefs:
    """Los valores recordados y quién los guarda (`None`: las pruebas, que no escriben)."""

    def __init__(self, values: dict | None = None, remember: Remember | None = None) -> None:
        self.values = dict(values or {})
        self._remember = remember

    @classmethod
    def from_config(cls, config: AppConfig, remember: Remember | None = None) -> Prefs:
        data = config.to_dict()
        return cls({key: data[key] for key in SHOWN}, remember)

    def get(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def save(self, key: str, value: object) -> None:
        if self.values.get(key) == value:
            return
        self.values[key] = value
        if self._remember is not None:
            self._remember(key, value)


def prefs_router(prefs: Prefs) -> APIRouter:
    router = APIRouter()

    @router.get("/api/prefs")
    async def get_prefs() -> dict:
        return dict(prefs.values)

    @router.post("/api/prefs")
    async def set_pref(body: PrefRequest) -> dict:
        allowed = VIEW_PREFS.get(body.key)
        if allowed is None:
            raise HTTPException(404, f"No se guarda «{body.key}» por aquí.")
        if body.value not in allowed:
            raise HTTPException(422, f"Valor no válido para {body.key}: {body.value}.")
        prefs.save(body.key, body.value)
        return dict(prefs.values)

    return router
