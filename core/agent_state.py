"""
Máquina de estados del módulo Agente (sin Qt).

Transiciones:
    idle | answered | error | start_marked -> mark_start -> start_marked
    start_marked -> mark_end  -> sending      (devuelve el rango ordenado)
    start_marked -> cancel    -> idle | answered
    sending      -> answered  -> answered
    sending      -> fail      -> error
    sending      -> cancel    -> idle | answered (se terminó la CLI a pedido)
    cualquiera salvo sending -> reset -> idle   (sesión nueva)

Un envío a la vez: mientras está enviando no se marca nada. Cambiar de interlocutor
es `cancel`: borra el inicio a medias, no las respuestas.
"""

from __future__ import annotations

from enum import StrEnum

from core.agent_selection import WordPos


class AgentState(StrEnum):
    IDLE = "idle"  # sin selección
    START_MARKED = "start_marked"  # inicio marcado, falta el final
    SENDING = "sending"  # esperando la respuesta de Claude
    ANSWERED = "answered"  # llegó la última respuesta
    ERROR = "error"  # el último envío falló; el motivo va en `message`


class AgentLogic:
    def __init__(self) -> None:
        self.state = AgentState.IDLE
        self.start: WordPos | None = None
        self.message = ""
        self.model = ""
        self.answers = 0

    @property
    def can_mark(self) -> bool:
        return self.state is not AgentState.SENDING

    @property
    def status(self) -> str:
        """Texto corto para la línea de estado."""
        if self.state is AgentState.START_MARKED:
            return "Inicio marcado: clic derecho en el final para enviar (Esc cancela)"
        if self.state is AgentState.SENDING:
            return f"Enviando a {self.model}..." if self.model else "Enviando..."
        if self.state is AgentState.ANSWERED:
            return "Respuesta lista: clic izquierdo para marcar otro inicio"
        if self.state is AgentState.ERROR:
            return f"Error: {self.message}"
        return "Clic izquierdo marca el inicio"

    def mark_start(self, pos: WordPos) -> bool:
        if not self.can_mark:
            return False
        self.start = pos
        self.state = AgentState.START_MARKED
        return True

    def mark_end(self, pos: WordPos, model: str = "") -> tuple[WordPos, WordPos] | None:
        """Cierra el rango y pasa a enviando; None si no había inicio marcado."""
        if self.state is not AgentState.START_MARKED or self.start is None:
            return None
        start, end = sorted((self.start, pos))
        self.start = None
        self.model = model
        self.state = AgentState.SENDING
        return start, end

    def cancel(self) -> bool:
        if self.state not in (AgentState.START_MARKED, AgentState.SENDING):
            return False
        self.start = None
        self.state = self._rest()
        return True

    def answered(self) -> None:
        if self.state is AgentState.SENDING:
            self.answers += 1
            self.state = AgentState.ANSWERED

    def fail(self, message: str) -> None:
        if self.state is AgentState.SENDING:
            self.message = message
            self.state = AgentState.ERROR

    def reset(self) -> bool:
        """Sesión nueva: olvida la selección y las respuestas."""
        if self.state is AgentState.SENDING:
            return False
        self.state = AgentState.IDLE
        self.start = None
        self.message = ""
        self.answers = 0
        return True

    def _rest(self) -> AgentState:
        return AgentState.ANSWERED if self.answers else AgentState.IDLE
