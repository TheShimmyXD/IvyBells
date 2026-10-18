"""
Modo anticipado del Agente: cuándo termina el turno del interlocutor y qué parte de
la conversación se le muestra a Claude. Sin Qt: el reloj llega como argumento.

El turno queda pendiente desde la primera frase final del interlocutor sin enviar y vence
tras `TURN_SILENCE_S` sin frase final ni provisional suyo, o en cuanto habla el otro canal.
Si el interlocutor retoma (aparece su provisional), el coordinador cancela el envío en
curso, o deja como superada la respuesta mostrada hace menos de `SUPERSEDE_S`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.live_view import Line

MANUAL, AHEAD = "manual", "ahead"
AGENT_MODES = (MANUAL, AHEAD)
TURN_SILENCE_S = 1.5
SUPERSEDE_S = 3.0
# Lo que contesta Claude cuando no hay nada que responder; no se muestra.
NO_ANSWER = "-"


class TurnEvent(StrEnum):
    NONE = "none"
    RESUMED = "resumed"  # el interlocutor volvió a hablar
    CLOSED = "closed"  # habló el otro canal: el turno pendiente se cierra ya


class TurnWatcher:
    def __init__(self, silence_s: float = TURN_SILENCE_S) -> None:
        self.silence_s = silence_s
        self.pending = False
        self.last_final = 0.0
        self._speaking = False
        self._closed_early = False

    def update(self, is_speaker: bool, new_final: bool, has_partial: bool, now: float) -> TurnEvent:
        """Un cambio en la transcripción de una fuente: frase final nueva o provisional."""
        if not is_speaker:
            if has_partial and self.pending and not self._closed_early:
                self._closed_early = True
                return TurnEvent.CLOSED
            return TurnEvent.NONE
        if new_final:
            self.pending = True
            self.last_final = now
        started = has_partial and not self._speaking
        self._speaking = has_partial
        return TurnEvent.RESUMED if started else TurnEvent.NONE

    def due(self, now: float) -> bool:
        if not self.pending or self._speaking:
            return False
        return self._closed_early or now - self.last_final >= self.silence_s

    def taken(self) -> None:
        """El turno se envió."""
        self.pending = False
        self._closed_early = False

    def reopen(self) -> None:
        """Se canceló o quedó superado lo enviado: el turno vuelve a quedar pendiente."""
        self.pending = True

    def reset(self) -> None:
        self.pending = False
        self._speaking = False
        self._closed_early = False


def shown_answer(text: str) -> str:
    """La respuesta tal como se muestra; vacía si es "-" (o todavía solo eso)."""
    stripped = text.strip()
    return "" if not stripped.strip(NO_ANSWER + "–— .") else stripped


def supersedes(done_at: float, now: float) -> bool:
    """Si el interlocutor retoma ahora, ¿la respuesta terminada en `done_at` queda superada?"""
    return now - done_at < SUPERSEDE_S


class Speaker(StrEnum):
    CLIENT = "client"  # el interlocutor
    OTHER = "other"  # el otro canal abierto
    SUGGESTION = "suggestion"  # una respuesta de Claude ya mostrada


@dataclass(frozen=True, slots=True)
class Said:
    clock: str
    speaker: Speaker
    text: str


def conversation(
    client: list[Line], other: list[Line], suggestions: list[tuple[str, str]]
) -> list[Said]:
    """Todo en orden de hora (a igual hora, primero lo dicho); `suggestions` es (hora, texto)."""
    said = [Said(line.clock, Speaker.CLIENT, line.text) for line in client]
    said += [Said(line.clock, Speaker.OTHER, line.text) for line in other]
    said += [Said(clock, Speaker.SUGGESTION, text) for clock, text in suggestions]
    return sorted(said, key=lambda item: (item.clock, item.speaker is Speaker.SUGGESTION))
