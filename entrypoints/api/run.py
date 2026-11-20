"""
API local de IvyBells (``main.py --api``) sobre ``jacck_common.webapi``.

``GET /api/health``, la escucha en vivo (``listening.py``), el Agente (``agent.py``), el
chat (``chat.py``), la configuración de Claude con perfiles y contextos (``settings.py``) y
lo recordado (``prefs.py``): token, Origin de la ventana de Tauri o del Vite de ``web/``,
puerto anunciado y apagado al cerrarse la entrada estándar.
"""

from __future__ import annotations

import logging
import tomllib

from fastapi import FastAPI, Request
from jacck_common.webapi.names import SidecarNames
from jacck_common.webapi.security import allowed_origins
from jacck_common.webapi.serve import serve, session_token
from jacck_common.webapi.server import KEEPALIVE_SECONDS, create_base_api

from app.agent import AgentAssistant
from app.chat import ChatAssistant
from app.live import LiveListening
from app.settings import ClaudeOptions
from app.wiring import build_claude_options, build_live
from entrypoints.api.agent import agent_router, live_followers
from entrypoints.api.chat import chat_router
from entrypoints.api.listening import listening_router
from entrypoints.api.owner import LoopOwner
from entrypoints.api.prefs import Prefs, prefs_router
from entrypoints.api.settings import SettingsFollowers, settings_router
from paths import API_SESSION_JSON, ROOT

logger = logging.getLogger(__name__)

NAMES = SidecarNames("IVYBELLS")
# El de web/vite.config.ts (5173 es el de Venona: se pueden tener las dos abiertas).
VITE_PORT = 5174


def app_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def create_api(
    token: str,
    listening: LiveListening,
    agent: AgentAssistant | None = None,
    chat: ChatAssistant | None = None,
    keepalive: float = KEEPALIVE_SECONDS,
    options: ClaudeOptions | None = None,
    prefs: Prefs | None = None,
) -> FastAPI:
    """
    La API con la escucha y, si se dan, el Agente, el chat y la configuración de Claude
    sobre esa misma escucha. Con `prefs`, el Agente empieza con el interlocutor y el modo
    recordados y cada elección del autor se guarda.
    """
    prefs = prefs or Prefs()
    version = app_version()
    api = create_base_api(
        title="IvyBells",
        token=token,
        allowed_origins=allowed_origins(VITE_PORT),
        health=lambda: {"version": version},
    )
    owner = LoopOwner()

    @api.middleware("http")
    async def bind_owner(request: Request, call_next):
        owner.bind()
        return await call_next(request)

    followers = live_followers(agent) if agent is not None else None
    router, channel = listening_router(listening, owner, keepalive, followers, prefs.save)
    api.include_router(router)
    api.state.listening_channel = channel
    api.include_router(prefs_router(prefs))
    if agent is not None:
        router, api.state.agent_channel = agent_router(agent, owner, keepalive, prefs.save)
        api.include_router(router)
        # Después de `attach`: el pulso del anticipado entrega al bucle de la API.
        agent.set_speaker(str(prefs.get("speaker", agent.speaker)))
        agent.set_mode(str(prefs.get("agent_mode", agent.mode)))
    if chat is not None:
        router, api.state.chat_channel = chat_router(chat, owner, keepalive)
        api.include_router(router)
    if options is not None:
        router, api.state.settings_channel = settings_router(
            options, owner, keepalive, settings_followers(agent, chat)
        )
        api.include_router(router)
    return api


def settings_followers(
    agent: AgentAssistant | None, chat: ChatAssistant | None
) -> SettingsFollowers:
    """Lo que el Agente y el chat oyen de la configuración, como los conecta la ventana."""

    def on_config() -> None:
        if agent is not None:
            agent.refresh_budget()
        if chat is not None:
            chat.on_settings_changed()

    def on_profile() -> None:
        if agent is not None:
            agent.refresh_budget()

    def on_context(payload: dict) -> None:
        if agent is not None:
            agent.on_context_reloaded(payload)

    return SettingsFollowers(config=on_config, profile=on_profile, context=on_context)


def run_api() -> int:
    """Corre la API hasta que la ventana la cierre (o Ctrl+C); al final cierra todo."""
    from config import load_app_config, save_app_config

    config = load_app_config()

    def remember(key: str, value: object) -> None:
        setattr(config, key, value)
        save_app_config(config)

    options = build_claude_options(
        config.claude, config.agent_profile, config.agent_context, remember
    )
    listening = build_live(config.closed_sources)
    agent = AgentAssistant(listening, options)
    chat = ChatAssistant(listening, options, config.chat_model, config.chat_effort, remember)
    token = session_token(NAMES)

    def stop() -> None:
        # Antes de borrar la sesión: sin procesos de claude ni hilos de la escucha.
        agent.close()
        chat.close()
        options.close()
        listening.close()

    prefs = Prefs.from_config(config, remember)
    api = create_api(token, listening, agent, chat, options=options, prefs=prefs)
    return serve(api, names=NAMES, token=token, session_path=API_SESSION_JSON, on_stop=stop)
