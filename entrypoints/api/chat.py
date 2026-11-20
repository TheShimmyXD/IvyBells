"""
Rutas del chat propio del autor y su canal de eventos.

`ChatAssistant` lleva el envío y su cancelación; sus avisos se vuelven eventos:
`turns` (cuántos turnos y el último, con la respuesta tal como llega), `sending` y
`config` (modelo y esfuerzo del chat).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from jacck_common.webapi.events import EventChannel
from jacck_common.webapi.server import KEEPALIVE_SECONDS, sse_response
from pydantic import BaseModel, Field

from app.chat import ChatAssistant, ChatListeners, ChatTurn
from entrypoints.api.owner import LoopOwner


class SendRequest(BaseModel):
    text: str = Field(min_length=1)


class ModelRequest(BaseModel):
    model: str


class EffortRequest(BaseModel):
    effort: str


def turn_data(turn: ChatTurn) -> dict:
    return {
        "clock": turn.clock,
        "request": turn.request,
        "model": turn.model,
        "effort": turn.effort,
        "answer": turn.answer,
        "error": turn.error,
        "cancelled": turn.cancelled,
        "done": turn.done,
        "first_text_s": None if turn.first_text_s is None else round(turn.first_text_s, 3),
    }


def brief(chat: ChatAssistant) -> dict:
    return {"model": chat.model, "effort": chat.effort, "sending": chat.sending}


def turns_data(chat: ChatAssistant) -> dict:
    last = chat.turns[-1] if chat.turns else None
    return {"count": len(chat.turns), "last": None if last is None else turn_data(last)}


def chat_snapshot(chat: ChatAssistant, channel: EventChannel) -> dict:
    count, _, _ = channel.state()
    return {
        **brief(chat),
        "turns": [turn_data(turn) for turn in chat.turns],
        "last_event": count,
    }


def chat_router(
    chat: ChatAssistant, owner: LoopOwner, keepalive: float = KEEPALIVE_SECONDS
) -> tuple[APIRouter, EventChannel]:
    router = APIRouter()
    channel = EventChannel()
    chat.attach(
        owner,
        ChatListeners(
            turns=lambda: channel.emit("turns", turns_data(chat)),
            sending=lambda sending: channel.emit("sending", {"sending": sending}),
            config=lambda _config: channel.emit("config", brief(chat)),
        ),
    )

    @router.get("/api/chat")
    async def get_chat() -> dict:
        return chat_snapshot(chat, channel)

    @router.post("/api/chat/send")
    async def send(body: SendRequest) -> dict:
        # False si ya hay un envío o el texto queda vacío.
        return {"sent": chat.send(body.text), **brief(chat)}

    @router.post("/api/chat/cancel")
    async def cancel() -> dict:
        chat.cancel()
        return brief(chat)

    @router.post("/api/chat/clear")
    async def clear() -> dict:
        chat.clear()
        return brief(chat)

    @router.post("/api/chat/model")
    async def set_model(body: ModelRequest) -> dict:
        chat.set_model(body.model)
        return brief(chat)

    @router.post("/api/chat/effort")
    async def set_effort(body: EffortRequest) -> dict:
        chat.set_effort(body.effort)
        return brief(chat)

    @router.get("/api/chat/events")
    def events(request: Request) -> StreamingResponse:
        return sse_response(channel.events_after, request, keepalive)

    return router, channel
