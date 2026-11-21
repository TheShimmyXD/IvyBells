"""
Rutas del Agente y su canal de eventos.

`AgentAssistant` ya lleva todo el ciclo (modos, marcas, historial, presupuesto, un envío a
la vez y la cancelación que termina el proceso de `claude`); aquí solo se piden sus
órdenes y sus avisos se vuelven eventos de un `EventChannel`: `state` (estado y texto de
estado), `turns` (cuántos turnos y el último, con la respuesta tal como va llegando),
`marks` (interlocutor, inicio marcado y rangos enviados), `budget` y `mode`.
El snapshot trae además `turn_silence_s`, el silencio que cierra un turno en anticipado.

Los avisos de la escucha le llegan con `live_followers` (sesión nueva, texto y canales).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from jacck_common.webapi.events import EventChannel
from jacck_common.webapi.server import KEEPALIVE_SECONDS, sse_response
from pydantic import BaseModel

from app.agent import AgentAssistant, AgentListeners, AgentTurn
from app.background import ignore
from app.live import LiveListeners
from domain.agent.agent_ahead import AGENT_MODES, TURN_SILENCE_S, shown_answer
from domain.agent.agent_selection import WordPos
from domain.agent.context_budget import ContextBudget
from domain.transcription.live_view import SOURCES
from entrypoints.api.owner import LoopOwner
from entrypoints.api.prefs import Remember


class MarkRequest(BaseModel):
    """Frase final del interlocutor y posición en caracteres dentro de su texto."""

    phrase: int
    offset: int


class ModeRequest(BaseModel):
    mode: str


class SpeakerRequest(BaseModel):
    source: str


def _seconds(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def pos_data(pos: WordPos | None) -> dict | None:
    return None if pos is None else {"phrase": pos.phrase, "word": pos.word}


def turn_data(turn: AgentTurn) -> dict:
    return {
        "source": turn.source,
        "model": turn.model,
        "mode": turn.mode,
        "clock": turn.clock,
        "done_clock": turn.done_clock,
        "fragment": turn.selection.text(),
        "start": pos_data(turn.selection.start),
        "end": pos_data(turn.selection.end),
        "answer": shown_answer(turn.answer),
        "error": turn.error,
        "cancelled": turn.cancelled,
        "done": turn.done,
        "superseded": turn.superseded,
        "first_text_s": _seconds(turn.first_text_s),
    }


def budget_data(budget: ContextBudget | None) -> dict | None:
    """Las cifras y los textos de la barra de contexto, para que la web no los repita."""
    if budget is None:
        return None
    return {
        "parts": [asdict(part) for part in budget.parts],
        "estimated_tokens": budget.estimated_tokens,
        "window": budget.window,
        "level": budget.level,
        "summary": budget.summary(),
        "short_summary": budget.summary(short=True),
        "last_summary": budget.last_summary(),
        "last": None if budget.last is None else asdict(budget.last),
        "first_text_s": _seconds(budget.first_text_s),
    }


def brief(agent: AgentAssistant) -> dict:
    return {
        "state": agent.logic.state,
        "status": agent.status,
        "mode": agent.mode,
        "speaker": agent.speaker,
        "busy": agent.busy,
    }


def marks_data(agent: AgentAssistant) -> dict:
    return {
        "speaker": agent.speaker,
        "start_mark": pos_data(agent.start_mark),
        "sent": {
            source: [[pos_data(start), pos_data(end)] for start, end in agent.sent_ranges(source)]
            for source in SOURCES
        },
    }


def turns_data(agent: AgentAssistant) -> dict:
    last = agent.turns[-1] if agent.turns else None
    return {"count": len(agent.turns), "last": None if last is None else turn_data(last)}


def agent_snapshot(agent: AgentAssistant, channel: EventChannel) -> dict:
    count, _, _ = channel.state()
    return {
        **brief(agent),
        **marks_data(agent),
        "budget": budget_data(agent.budget),
        "turns": [turn_data(turn) for turn in agent.turns],
        "turn_silence_s": TURN_SILENCE_S,
        "last_event": count,
    }


def live_followers(agent: AgentAssistant) -> LiveListeners:
    """Lo que el Agente oye de la escucha, como lo conecta la ventana."""
    return LiveListeners(
        session_started=agent.reset,
        sources=agent.on_sources_changed,
        transcript=agent.on_transcript,
    )


def agent_router(
    agent: AgentAssistant,
    owner: LoopOwner,
    keepalive: float = KEEPALIVE_SECONDS,
    remember: Remember | None = None,
) -> tuple[APIRouter, EventChannel]:
    """`remember` guarda el modo y el interlocutor que elige el autor."""
    save = remember or ignore
    router = APIRouter()
    channel = EventChannel()
    agent.attach(
        owner,
        AgentListeners(
            state=lambda _payload: channel.emit("state", brief(agent)),
            turns=lambda: channel.emit("turns", turns_data(agent)),
            marks=lambda: channel.emit("marks", marks_data(agent)),
            budget=lambda: channel.emit("budget", budget_data(agent.budget) or {}),
            mode=lambda mode: channel.emit("mode", {"mode": mode}),
        ),
    )

    @router.get("/api/agent")
    async def get_agent() -> dict:
        return agent_snapshot(agent, channel)

    @router.post("/api/agent/mode")
    async def set_mode(body: ModeRequest) -> dict:
        if body.mode not in AGENT_MODES:
            raise HTTPException(422, f"Modo desconocido: {body.mode}.")
        agent.set_mode(body.mode)
        save("agent_mode", agent.mode)
        return brief(agent)

    @router.post("/api/agent/speaker")
    async def set_speaker(body: SpeakerRequest) -> dict:
        if body.source not in SOURCES:
            raise HTTPException(404, f"No hay canal «{body.source}».")
        agent.set_speaker(body.source)
        save("speaker", agent.speaker)
        return brief(agent)

    @router.post("/api/agent/mark_start")
    async def mark_start(body: MarkRequest) -> dict:
        agent.mark_start(body.phrase, body.offset)
        return {**brief(agent), "start_mark": pos_data(agent.start_mark)}

    @router.post("/api/agent/mark_end")
    async def mark_end(body: MarkRequest) -> dict:
        agent.mark_end(body.phrase, body.offset)
        return brief(agent)

    @router.post("/api/agent/cancel")
    async def cancel() -> dict:
        agent.cancel()
        return brief(agent)

    @router.post("/api/agent/reset")
    async def reset() -> dict:
        agent.reset()
        return brief(agent)

    @router.get("/api/agent/events")
    def events(request: Request) -> StreamingResponse:
        return sse_response(channel.events_after, request, keepalive)

    return router, channel
