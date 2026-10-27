"""
Coordinador del chat propio del autor, en la columna derecha del módulo Agente.

Sin perfil: el system prompt son las reglas del chat y el contexto del proyecto. Cada
petición lleva la transcripción de los dos canales de la misma escucha en vivo (sin las
respuestas del agente) y el historial del chat. El modelo y el esfuerzo son propios y se
recuerdan aparte; la cuenta, el respaldo y el ejecutable salen de `ClaudeSettings`.
Usa el mismo worker que el agente, en su propio hilo: los dos pueden enviar a la vez.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal, Slot

from coordinator_config import ClaudeSettings
from coordinator_live import LiveCoordinator
from core.chat_prompt import (
    DEFAULT_CHAT_EFFORT,
    DEFAULT_CHAT_MODEL,
    ChatExchange,
    Spoken,
    build_chat_prompt,
    build_chat_system_prompt,
    chat_model_config,
    spoken_lines,
)
from core.claude_model import EFFORT_LEVELS, ClaudeModelConfig, is_valid_model
from core.live_view import SOURCES
from core.transcript_markdown import SOURCE_LABELS
from services.service_claude import ClaudeCli, ClaudeService
from workers.worker_agent import AgentWorker
from workers.worker_runner import RequestSequence, start_worker, stop_thread

logger = logging.getLogger(__name__)

CLOSE_TIMEOUT_MS = 5_000

# Recibe el modelo y el system prompt (reglas del chat y contexto).
ServiceFactory = Callable[[ClaudeModelConfig, str], ClaudeService]


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


class ChatCoordinator(QObject):
    """
    Signals
    -------
    turns_changed()          -> cambió la lista de peticiones o la respuesta en curso.
    sending_changed(bool)    -> empezó o terminó un envío.
    config_changed(object)   -> el `ClaudeModelConfig` del chat (modelo, esfuerzo o cuenta).
    """

    turns_changed = Signal()
    sending_changed = Signal(bool)
    config_changed = Signal(object)

    def __init__(
        self,
        live: LiveCoordinator,
        settings: ClaudeSettings,
        model: str = DEFAULT_CHAT_MODEL,
        effort: str = DEFAULT_CHAT_EFFORT,
        remember: Callable[[str, object], object] | None = None,
        service_factory: ServiceFactory = ClaudeCli,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.live = live
        self.settings = settings
        self.model = model if is_valid_model(model) else DEFAULT_CHAT_MODEL
        self.effort = effort if effort in EFFORT_LEVELS else DEFAULT_CHAT_EFFORT
        self.turns: list[ChatTurn] = []
        self._remember = remember
        self._service_factory = service_factory
        self._clock = clock
        self._requests = RequestSequence()
        self._cancel = threading.Event()
        self._worker: AgentWorker | None = None
        self._thread: QThread | None = None
        settings.config_changed.connect(lambda _config: self.config_changed.emit(self.config))

    # -- Pedidos de la vista -----------------------------------

    @property
    def config(self) -> ClaudeModelConfig:
        return chat_model_config(self.settings.config, self.model, self.effort)

    @property
    def sending(self) -> bool:
        return self._thread is not None

    @property
    def last_first_text_s(self) -> float | None:
        for turn in reversed(self.turns):
            if turn.first_text_s is not None:
                return turn.first_text_s
        return None

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
        self.turns_changed.emit()
        self.sending_changed.emit(True)
        return True

    def cancel(self) -> None:
        if self.sending:
            self._cancel.set()

    def clear(self) -> None:
        """Vacía el chat; un envío en curso se cancela."""
        self.cancel()
        self.turns.clear()
        self.turns_changed.emit()

    def close(self) -> None:
        """Cancela el envío en curso y espera al worker; la ventana lo llama al cerrarse."""
        self._cancel.set()
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker (llegan en el hilo principal) ------

    def _current(self) -> ChatTurn | None:
        return self.turns[-1] if self.turns and not self.turns[-1].done else None

    @Slot(str)
    def on_text(self, chunk: str) -> None:
        turn = self._current()
        if turn is None:
            return
        if turn.first_text_s is None:
            turn.first_text_s = self._clock() - turn.sent_at
        turn.answer += chunk
        self.turns_changed.emit()

    @Slot(str)
    def on_failed(self, message: str) -> None:
        turn = self._current()
        if turn is not None:
            turn.error = message
            self.turns_changed.emit()

    @Slot(dict)
    def on_finished(self, payload: dict) -> None:
        if not self._requests.is_current(payload):
            return
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
        self.turns_changed.emit()

    # -- Internos ----------------------------------------------

    def _changed(self, key: str, value: str) -> None:
        if self._remember is not None:
            self._remember(key, value)
        self.config_changed.emit(self.config)

    def _spoken(self) -> list[Spoken]:
        finals = self.live.transcript.finals
        return spoken_lines({SOURCE_LABELS[source]: finals(source) for source in SOURCES})

    def _launch(self, config: ClaudeModelConfig, prompt: str) -> None:
        self._cancel = threading.Event()
        worker = self._worker = AgentWorker(
            service=self._service_factory(
                config, build_chat_system_prompt(self.settings.context.text())
            ),
            prompt=prompt,
            cancel_event=self._cancel,
            request_id=self._requests.next(),
        )
        worker.text.connect(self.on_text)
        worker.failed.connect(self.on_failed)
        self._thread = start_worker(
            self, worker, on_done=self.on_finished, on_cleared=self._clear_refs
        )

    def _clear_refs(self) -> None:
        self._worker = None
        self._thread = None
        self.sending_changed.emit(False)
