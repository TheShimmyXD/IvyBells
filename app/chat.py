"""
Chat propio del autor (la columna derecha del módulo Agente).

Sin perfil: el system prompt son las reglas del chat y el contexto del proyecto. Cada
petición lleva la transcripción de los dos canales de la misma escucha en vivo (sin las
respuestas del agente) y el historial del chat. El modelo y el esfuerzo son propios y se
recuerdan aparte; la cuenta, el respaldo y el ejecutable salen de `ClaudeSetup`. Tiene su
propio `AskSlot`: el Agente y el chat pueden enviar a la vez.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.claude_ask import AskCallbacks, AskSlot, ClaudeSetup, LiveText, ServiceFactory, claude_cli
from app.live import Post, call_now
from domain.agent.chat_prompt import (
    DEFAULT_CHAT_EFFORT,
    DEFAULT_CHAT_MODEL,
    ChatExchange,
    Spoken,
    build_chat_prompt,
    build_chat_system_prompt,
    chat_model_config,
    spoken_lines,
)
from domain.claude.claude_model import EFFORT_LEVELS, ClaudeModelConfig, is_valid_model
from domain.transcription.live_view import SOURCES
from domain.transcription.transcript_markdown import SOURCE_LABELS

logger = logging.getLogger(__name__)

CLOSE_TIMEOUT_S = 5.0


def _ignore(*_args: object) -> None:
    pass


@dataclass(slots=True)
class ChatTurn:
    """Una petición del autor y lo que llega de la respuesta."""

    clock: str
    request: str
    model: str
    effort: str
    sent_at: float = 0.0
    first_text_s: float | None = None
    answer: str = ""
    error: str = ""
    cancelled: bool = False
    done: bool = False

    @property
    def counts(self) -> bool:
        """Si entra al historial: terminada, sin cancelar ni error y con texto."""
        return self.done and not (self.cancelled or self.error) and bool(self.answer.strip())


@dataclass
class ChatListeners:
    """
    Avisos del chat a su dueño, siempre en el hilo dueño. Por defecto no hacen nada.

    turns()                   -> cambió la lista de peticiones o la respuesta en curso.
    sending(bool)             -> empezó o terminó un envío.
    config(ClaudeModelConfig) -> el modelo del chat (modelo, esfuerzo o cuenta).
    """

    turns: Callable[[], None] = _ignore
    sending: Callable[[bool], None] = _ignore
    config: Callable[[ClaudeModelConfig], None] = _ignore


class ChatAssistant:
    """Caso de uso del chat; se usa desde un solo hilo (el dueño)."""

    def __init__(
        self,
        live: LiveText,
        setup: ClaudeSetup,
        model: str = DEFAULT_CHAT_MODEL,
        effort: str = DEFAULT_CHAT_EFFORT,
        remember: Callable[[str, object], object] | None = None,
        service_factory: ServiceFactory = claude_cli,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.live = live
        self.setup = setup
        self.model = model if is_valid_model(model) else DEFAULT_CHAT_MODEL
        self.effort = effort if effort in EFFORT_LEVELS else DEFAULT_CHAT_EFFORT
        self.turns: list[ChatTurn] = []
        self.listeners = ChatListeners()
        self._post: Post = call_now
        self._remember = remember
        self._service_factory = service_factory
        self._clock = clock
        self._ask = AskSlot()

    def attach(self, post: Post, listeners: ChatListeners) -> None:
        """Fija el hilo dueño y quién recibe los avisos; la puerta lo llama una vez al armarse."""
        self._post = post
        self.listeners = listeners

    # -- Lo que lee la puerta ----------------------------------

    @property
    def config(self) -> ClaudeModelConfig:
        return chat_model_config(self.setup.config, self.model, self.effort)

    @property
    def sending(self) -> bool:
        return self._ask.busy

    @property
    def last_first_text_s(self) -> float | None:
        for turn in reversed(self.turns):
            if turn.first_text_s is not None:
                return turn.first_text_s
        return None

    # -- Pedidos de la puerta ----------------------------------

    def set_model(self, model: str) -> None:
        if model == self.model or not is_valid_model(model):
            return
        self.model = model
        self._changed("chat_model", model)

    def set_effort(self, effort: str) -> None:
        if effort == self.effort or effort not in EFFORT_LEVELS:
            return
        self.effort = effort
        self._changed("chat_effort", effort)

    def send(self, text: str) -> bool:
        """Envía una petición; no hace nada si está vacía o si hay otra en curso."""
        request = text.strip()
        if not request or self.sending:
            return False
        history = [
            ChatExchange(turn.clock, turn.request, turn.answer)
            for turn in self.turns
            if turn.counts
        ]
        config = self.config
        turn = ChatTurn(
            f"{datetime.now():%H:%M:%S}", request, config.model, config.effort, self._clock()
        )
        self.turns.append(turn)
        prompt = build_chat_prompt(self._spoken(), history, request)
        self._launch(config, prompt)
        self.listeners.turns()
        self.listeners.sending(True)
        return True

    def cancel(self) -> None:
        if self.sending:
            self._ask.cancel()

    def clear(self) -> None:
        """Vacía el chat; un envío en curso se cancela."""
        self.cancel()
        self.turns.clear()
        self.listeners.turns()

    def close(self, timeout_s: float = CLOSE_TIMEOUT_S) -> None:
        """Cancela el envío en curso y espera a su hilo; la puerta lo llama al cerrarse."""
        self._ask.close(timeout_s)

    def on_settings_changed(self) -> None:
        """La cuenta o el respaldo cambiaron en Configuración: cambia el modelo del chat."""
        self.listeners.config(self.config)

    # -- Avisos del envío (ya en el hilo dueño) ----------------

    def _current(self) -> ChatTurn | None:
        return self.turns[-1] if self.turns and not self.turns[-1].done else None

    def on_text(self, chunk: str) -> None:
        turn = self._current()
        if turn is None:
            return
        if turn.first_text_s is None:
            turn.first_text_s = self._clock() - turn.sent_at
        turn.answer += chunk
        self.listeners.turns()

    def on_failed(self, message: str) -> None:
        turn = self._current()
        if turn is not None:
            turn.error = message
            self.listeners.turns()

    def on_finished(self, payload: dict) -> None:
        turn = self._current()
        if turn is None:
            return
        turn.done = True
        if payload.get("cancelled"):
            turn.cancelled = True
        elif not turn.error:
            turn.answer = payload.get("answer") or turn.answer
            logger.info(
                "Chat: %s %s, primer texto %s s, total %.2f s",
                turn.model,
                turn.effort or "por defecto",
                "-" if turn.first_text_s is None else f"{turn.first_text_s:.2f}",
                self._clock() - turn.sent_at,
            )
        self.listeners.turns()

    # -- Internos ----------------------------------------------

    def _changed(self, key: str, value: str) -> None:
        if self._remember is not None:
            self._remember(key, value)
        self.listeners.config(self.config)

    def _spoken(self) -> list[Spoken]:
        finals = self.live.transcript.finals
        return spoken_lines({SOURCE_LABELS[source]: finals(source) for source in SOURCES})

    def _launch(self, config: ClaudeModelConfig, prompt: str) -> None:
        service = self._service_factory(config, build_chat_system_prompt(self.setup.context.text()))
        self._ask.launch(
            service,
            prompt,
            self._post,
            AskCallbacks(text=self.on_text, failed=self.on_failed, finished=self.on_finished),
            on_cleared=lambda: self.listeners.sending(False),
        )
