"""
Rutas de la configuración de Claude, la cuenta, los perfiles y los contextos del Agente.

`ClaudeOptions` lleva todo (guardar, comprobar la cuenta en su hilo, rehacer la foto del
contexto en el suyo); aquí solo se piden sus órdenes y sus avisos se vuelven eventos de un
`EventChannel`: `config`, `account` (`text`, `level`, `login`), `profiles` (lista y perfil
en uso), `profile_notice`, `contexts` (lista, en uso, carpeta y peso) y `context_reloaded`.

Los mismos avisos le llegan al Agente y al chat con `SettingsFollowers`, como los conecta
la ventana: el presupuesto se rehace con el modelo, el perfil y la foto nuevos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from jacck_common.webapi.events import EventChannel
from jacck_common.webapi.server import KEEPALIVE_SECONDS, sse_response
from pydantic import BaseModel, Field

from app.context import ContextListeners
from app.profiles import ProfileListeners
from app.settings import (
    CLAUDE_MODELS,
    EFFORTS,
    FALLBACKS,
    TIMEOUTS_S,
    ClaudeOptions,
    SettingsListeners,
)
from domain.claude.claude_model import EFFORT_LEVELS, ClaudeModelConfig, is_valid_model
from entrypoints.api.owner import LoopOwner

NOT_CHECKED = {"text": "Sin comprobar", "level": "info", "login": ""}


def _nothing() -> None:
    pass


def _ignore(*_args: object) -> None:
    pass


@dataclass
class SettingsFollowers:
    """
    Lo que el Agente y el chat oyen de la configuración. Por defecto no hacen nada.

    config()        -> cambió el modelo, el esfuerzo, el respaldo, el tiempo o la cuenta.
    profile()       -> cambió la lista de perfiles o el perfil en uso.
    context(dict)   -> la foto del contexto se está rehaciendo o ya se rehizo.
    """

    config: Callable[[], None] = _nothing
    profile: Callable[[], None] = _nothing
    context: Callable[[dict], None] = _ignore


class ValueRequest(BaseModel):
    value: str


class TimeoutRequest(BaseModel):
    seconds: int


class NameRequest(BaseModel):
    name: str


class TextRequest(BaseModel):
    text: str


class NewContextRequest(BaseModel):
    name: str = Field(default="nuevo contexto", min_length=1)


def config_data(config: ClaudeModelConfig) -> dict:
    return {
        "model": config.model,
        "effort": config.effort,
        "fallback_model": config.fallback_model,
        "timeout_s": config.timeout_s,
        "account": config.account,
    }


def choice_items(entries: tuple[tuple[str, str, str], ...]) -> list[dict]:
    """Las opciones de un selector como las pinta la web: clave, nombre y ayuda."""
    return [{"key": k, "label": label, "help": tip} for k, label, tip in entries]


def choices_data() -> dict:
    return {
        "models": choice_items(CLAUDE_MODELS),
        "efforts": choice_items(EFFORTS),
        "fallbacks": list(FALLBACKS),
        "timeouts_s": list(TIMEOUTS_S),
    }


def profiles_data(options: ClaudeOptions) -> dict:
    profiles = options.profiles
    return {
        "names": profiles.names(),
        "active": profiles.active,
        "editable": [name for name in profiles.names() if profiles.is_editable(name)],
    }


def contexts_data(options: ClaudeOptions) -> dict:
    context = options.context
    folder = context.folder
    return {
        "names": context.names(),
        "active": context.active,
        "folder": None if folder is None else str(folder),
        "target": str(context.target),
        "weights": context.weights(),
        "busy": context.is_busy(),
    }


def settings_router(
    options: ClaudeOptions,
    owner: LoopOwner,
    keepalive: float = KEEPALIVE_SECONDS,
    followers: SettingsFollowers | None = None,
) -> tuple[APIRouter, EventChannel]:
    router = APIRouter()
    channel = EventChannel()
    follow = followers or SettingsFollowers()
    # La última cuenta avisada y el último error de un pedido (para el detalle del 409).
    last = {"account": dict(NOT_CHECKED), "error": ""}

    def on_account(payload: dict) -> None:
        last["account"] = payload
        channel.emit("account", payload)

    def on_config(config: ClaudeModelConfig) -> None:
        channel.emit("config", config_data(config))
        follow.config()

    def on_profiles(*_args: object) -> None:
        channel.emit("profiles", profiles_data(options))
        follow.profile()

    def on_notice(payload: dict) -> None:
        if payload.get("level") == "error":
            last["error"] = payload.get("text", "")
        channel.emit("profile_notice", payload)

    def on_contexts(*_args: object) -> None:
        channel.emit("contexts", contexts_data(options))

    def on_reloaded(payload: dict) -> None:
        if payload.get("level") == "error":
            last["error"] = payload.get("text", "")
        channel.emit("context_reloaded", payload)
        if payload.get("level") != "busy":
            # El peso de cada archivo sale de la foto nueva.
            channel.emit("contexts", contexts_data(options))
        follow.context(payload)

    options.attach(owner, SettingsListeners(config=on_config, account=on_account))
    options.profiles.listeners = ProfileListeners(
        changed=on_profiles, active=on_profiles, notice=on_notice
    )
    options.context.attach(
        owner, ContextListeners(changed=on_contexts, active=on_contexts, reloaded=on_reloaded)
    )

    def attempt(action: Callable[[], object], default: str) -> object:
        """Corre el pedido; si falla, 409 con el motivo que avisó la biblioteca."""
        last["error"] = ""
        result = action()
        if not result:
            raise HTTPException(409, last["error"] or default)
        return result

    def known_profile(name: str) -> None:
        if name not in options.profiles.names():
            raise HTTPException(404, f"No hay perfil «{name}».")

    def known_context(name: str) -> None:
        if name not in options.context.names():
            raise HTTPException(404, f"No hay contexto «{name}».")

    # -- Configuración y cuenta --------------------------------

    @router.get("/api/settings")
    async def get_settings() -> dict:
        count, _, _ = channel.state()
        return {
            "config": config_data(options.config),
            "choices": choices_data(),
            "account": last["account"],
            "checking": options.is_busy(),
            "profiles": profiles_data(options),
            "contexts": contexts_data(options),
            "last_event": count,
        }

    @router.post("/api/settings/model")
    async def set_model(body: ValueRequest) -> dict:
        if not is_valid_model(body.value):
            raise HTTPException(422, f"Modelo desconocido: {body.value}.")
        options.set_model(body.value)
        return config_data(options.config)

    @router.post("/api/settings/effort")
    async def set_effort(body: ValueRequest) -> dict:
        if body.value not in EFFORT_LEVELS:
            raise HTTPException(422, f"Esfuerzo desconocido: {body.value}.")
        options.set_effort(body.value)
        return config_data(options.config)

    @router.post("/api/settings/fallback")
    async def set_fallback(body: ValueRequest) -> dict:
        if body.value not in FALLBACKS:
            raise HTTPException(422, f"Respaldo desconocido: {body.value}.")
        options.set_fallback(body.value)
        return config_data(options.config)

    @router.post("/api/settings/timeout")
    async def set_timeout(body: TimeoutRequest) -> dict:
        if body.seconds not in TIMEOUTS_S:
            raise HTTPException(422, f"Tiempo no válido: {body.seconds} s.")
        options.set_timeout(body.seconds)
        return config_data(options.config)

    @router.post("/api/settings/account")
    async def set_account(body: ValueRequest) -> dict:
        if not options.set_account(body.value):
            raise HTTPException(422, last["account"]["text"])
        return config_data(options.config)

    @router.post("/api/settings/account/check")
    async def check_account() -> dict:
        options.check()
        return {"checking": options.is_busy()}

    # -- Perfiles ----------------------------------------------

    @router.get("/api/profiles/{name}")
    async def get_profile(name: str) -> dict:
        known_profile(name)
        profiles = options.profiles
        return {"name": name, "text": profiles.text(name), "editable": profiles.is_editable(name)}

    @router.post("/api/profiles/active")
    async def set_active_profile(body: NameRequest) -> dict:
        known_profile(body.name)
        options.profiles.set_active(body.name)
        return profiles_data(options)

    @router.post("/api/profiles")
    async def create_profile() -> dict:
        name = attempt(options.profiles.create, "No se pudo crear el perfil.")
        return {"name": name, **profiles_data(options)}

    @router.post("/api/profiles/{name}/save")
    async def save_profile(name: str, body: TextRequest) -> dict:
        known_profile(name)
        attempt(lambda: options.profiles.save(name, body.text), f"No se guardó el perfil {name}.")
        return {"name": name, **profiles_data(options)}

    @router.post("/api/profiles/{name}/duplicate")
    async def duplicate_profile(name: str) -> dict:
        known_profile(name)
        copy = attempt(lambda: options.profiles.duplicate(name), f"No se copió el perfil {name}.")
        return {"name": copy, **profiles_data(options)}

    @router.post("/api/profiles/{name}/rename")
    async def rename_profile(name: str, body: NameRequest) -> dict:
        known_profile(name)
        renamed = attempt(
            lambda: options.profiles.rename(name, body.name), f"No se renombró el perfil {name}."
        )
        return {"name": renamed, **profiles_data(options)}

    @router.post("/api/profiles/{name}/delete")
    async def delete_profile(name: str) -> dict:
        known_profile(name)
        attempt(lambda: options.profiles.delete(name), f"No se borró el perfil {name}.")
        return profiles_data(options)

    # -- Contextos ---------------------------------------------

    @router.post("/api/contexts/active")
    async def set_active_context(body: NameRequest) -> dict:
        if body.name:
            known_context(body.name)
        options.context.set_active(body.name)
        return contexts_data(options)

    @router.post("/api/contexts")
    async def create_context(body: NewContextRequest) -> dict:
        name = attempt(
            lambda: options.context.create(body.name), f"No se creó el contexto {body.name}."
        )
        return {"name": name, **contexts_data(options)}

    @router.post("/api/contexts/{name}/rename")
    async def rename_context(name: str, body: NameRequest) -> dict:
        known_context(name)
        renamed = attempt(
            lambda: options.context.rename(name, body.name), f"No se renombró el contexto {name}."
        )
        return {"name": renamed, **contexts_data(options)}

    @router.post("/api/contexts/reload")
    async def reload_context() -> dict:
        options.context.reload()
        return contexts_data(options)

    @router.get("/api/settings/events")
    def events(request: Request) -> StreamingResponse:
        return sse_response(channel.events_after, request, keepalive)

    return router, channel
