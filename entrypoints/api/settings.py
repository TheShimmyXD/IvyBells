"""
Rutas de la configuración de Claude, la cuenta, los perfiles y los contextos del Agente.

`ClaudeOptions` lleva todo (guardar, comprobar la cuenta en su hilo, rehacer la foto del
contexto en el suyo); aquí solo se piden sus órdenes y sus avisos se vuelven eventos de un
`EventChannel`: `config`, `account` (`text`, `level`, `login`), `profiles` (lista y perfil
en uso), `profile_notice`, `contexts` (lista, en uso, carpeta y peso) y `context_reloaded`
(el último va también en el snapshot, como `context_notice`).

Los mismos avisos le llegan al Agente y al chat con `SettingsFollowers`, como los conecta
la ventana: el presupuesto se rehace con el modelo, el perfil y la foto nuevos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from jacck_common.webapi.events import EventChannel
from jacck_common.webapi.server import KEEPALIVE_SECONDS, sse_response
from pydantic import BaseModel, Field

from app.background import ignore
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
    context: Callable[[dict], None] = ignore


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


def context_entries(weights: dict[str, int]) -> list[dict]:
    """Lo que hay en la carpeta del contexto como lo pinta la web: nombre, tokens y si es carpeta."""
    return [
        {"name": Path(path).name or path, "tokens": tokens, "folder": Path(path).is_dir()}
        for path, tokens in weights.items()
    ]


def contexts_data(options: ClaudeOptions) -> dict:
    context = options.context
    folder = context.folder
    weights = context.weights()
    return {
        "names": context.names(),
        "active": context.active,
        "folder": None if folder is None else str(folder),
        "target": str(context.target),
        "weights": weights,
        "entries": context_entries(weights),
        "busy": context.is_busy(),
    }


class _Settings:
    """
    Lo que comparten las tres partes de las rutas: las opciones, el canal, a quién avisar
    y lo último avisado (la cuenta, la foto del contexto y el error de un pedido, para el
    detalle del 409).
    """

    def __init__(self, options: ClaudeOptions, follow: SettingsFollowers) -> None:
        self.options = options
        self.follow = follow
        self.channel = EventChannel()
        self.account: dict = dict(NOT_CHECKED)
        self.context: dict = {"text": "", "level": ""}
        self.error = ""

    def note_error(self, payload: dict) -> None:
        if payload.get("level") == "error":
            self.error = payload.get("text", "")

    def attempt(self, action: Callable[[], object], default: str) -> object:
        """Corre el pedido; si falla, 409 con el motivo que avisó la biblioteca."""
        self.error = ""
        result = action()
        if not result:
            raise HTTPException(409, self.error or default)
        return result


def _claude_routes(router: APIRouter, state: _Settings, owner: LoopOwner) -> None:
    """Modelo, esfuerzo, respaldo, tiempo y cuenta."""
    options, channel = state.options, state.channel

    def on_account(payload: dict) -> None:
        state.account = payload
        channel.emit("account", payload)

    def on_config(config: ClaudeModelConfig) -> None:
        channel.emit("config", config_data(config))
        state.follow.config()

    options.attach(owner, SettingsListeners(config=on_config, account=on_account))

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
            raise HTTPException(422, state.account["text"])
        return config_data(options.config)

    @router.post("/api/settings/account/check")
    async def check_account() -> dict:
        options.check()
        return {"checking": options.is_busy()}


def _profile_routes(router: APIRouter, state: _Settings) -> None:
    """Elegir, ver, crear, guardar, copiar, renombrar y borrar perfiles."""
    options, attempt = state.options, state.attempt
    profiles = options.profiles

    def on_profiles(*_args: object) -> None:
        state.channel.emit("profiles", profiles_data(options))
        state.follow.profile()

    def on_notice(payload: dict) -> None:
        state.note_error(payload)
        state.channel.emit("profile_notice", payload)

    profiles.listeners = ProfileListeners(changed=on_profiles, active=on_profiles, notice=on_notice)

    def known_profile(name: str) -> None:
        if name not in profiles.names():
            raise HTTPException(404, f"No hay perfil «{name}».")

    @router.get("/api/profiles/{name}")
    async def get_profile(name: str) -> dict:
        known_profile(name)
        return {"name": name, "text": profiles.text(name), "editable": profiles.is_editable(name)}

    @router.post("/api/profiles/active")
    async def set_active_profile(body: NameRequest) -> dict:
        known_profile(body.name)
        profiles.set_active(body.name)
        return profiles_data(options)

    @router.post("/api/profiles")
    async def create_profile() -> dict:
        name = attempt(profiles.create, "No se pudo crear el perfil.")
        return {"name": name, **profiles_data(options)}

    @router.post("/api/profiles/{name}/save")
    async def save_profile(name: str, body: TextRequest) -> dict:
        known_profile(name)
        attempt(lambda: profiles.save(name, body.text), f"No se guardó el perfil {name}.")
        return {"name": name, **profiles_data(options)}

    @router.post("/api/profiles/{name}/duplicate")
    async def duplicate_profile(name: str) -> dict:
        known_profile(name)
        copy = attempt(lambda: profiles.duplicate(name), f"No se copió el perfil {name}.")
        return {"name": copy, **profiles_data(options)}

    @router.post("/api/profiles/{name}/rename")
    async def rename_profile(name: str, body: NameRequest) -> dict:
        known_profile(name)
        renamed = attempt(
            lambda: profiles.rename(name, body.name), f"No se renombró el perfil {name}."
        )
        return {"name": renamed, **profiles_data(options)}

    @router.post("/api/profiles/{name}/delete")
    async def delete_profile(name: str) -> dict:
        known_profile(name)
        attempt(lambda: profiles.delete(name), f"No se borró el perfil {name}.")
        return profiles_data(options)


def _context_routes(router: APIRouter, state: _Settings, owner: LoopOwner) -> None:
    """Elegir, crear y renombrar contextos, abrir su carpeta o su foto y rehacerla."""
    options, attempt, channel = state.options, state.attempt, state.channel
    context = options.context

    def on_contexts(*_args: object) -> None:
        channel.emit("contexts", contexts_data(options))

    def on_reloaded(payload: dict) -> None:
        state.context = payload
        state.note_error(payload)
        channel.emit("context_reloaded", payload)
        if payload.get("level") != "busy":
            # El peso de cada archivo sale de la foto nueva.
            channel.emit("contexts", contexts_data(options))
        state.follow.context(payload)

    context.attach(
        owner, ContextListeners(changed=on_contexts, active=on_contexts, reloaded=on_reloaded)
    )

    def known_context(name: str) -> None:
        if name not in context.names():
            raise HTTPException(404, f"No hay contexto «{name}».")

    @router.post("/api/contexts/active")
    async def set_active_context(body: NameRequest) -> dict:
        if body.name:
            known_context(body.name)
        context.set_active(body.name)
        return contexts_data(options)

    @router.post("/api/contexts")
    async def create_context(body: NewContextRequest) -> dict:
        name = attempt(lambda: context.create(body.name), f"No se creó el contexto {body.name}.")
        return {"name": name, **contexts_data(options)}

    @router.post("/api/contexts/{name}/rename")
    async def rename_context(name: str, body: NameRequest) -> dict:
        known_context(name)
        renamed = attempt(
            lambda: context.rename(name, body.name), f"No se renombró el contexto {name}."
        )
        return {"name": renamed, **contexts_data(options)}

    @router.post("/api/contexts/open-folder")
    async def open_context_folder() -> dict:
        attempt(context.open_folder, "No se pudo abrir la carpeta del contexto.")
        return contexts_data(options)

    @router.post("/api/contexts/open-snapshot")
    async def open_context_snapshot() -> dict:
        attempt(context.open_snapshot, "No se pudo abrir contexto.md.")
        return contexts_data(options)

    @router.post("/api/contexts/reload")
    async def reload_context() -> dict:
        context.reload()
        return contexts_data(options)


def settings_router(
    options: ClaudeOptions,
    owner: LoopOwner,
    keepalive: float = KEEPALIVE_SECONDS,
    followers: SettingsFollowers | None = None,
) -> tuple[APIRouter, EventChannel]:
    """Las rutas de Claude y la cuenta, de los perfiles y de los contextos, con un canal."""
    router = APIRouter()
    state = _Settings(options, followers or SettingsFollowers())
    channel = state.channel

    @router.get("/api/settings")
    async def get_settings() -> dict:
        count, _, _ = channel.state()
        return {
            "config": config_data(options.config),
            "choices": choices_data(),
            "account": state.account,
            "checking": options.is_busy(),
            "profiles": profiles_data(options),
            "contexts": contexts_data(options),
            "context_notice": state.context,
            "last_event": count,
        }

    _claude_routes(router, state, owner)
    _profile_routes(router, state)
    _context_routes(router, state, owner)

    @router.get("/api/settings/events")
    def events(request: Request) -> StreamingResponse:
        return sse_response(channel.events_after, request, keepalive)

    return router, channel
