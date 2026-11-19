"""Corte de frases a partir de la probabilidad de voz que da el VAD por ventana."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PhraseEventKind(Enum):
    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class PhraseEvent:
    """Inicio o fin de una frase, en número de ventana del flujo (0 = la primera)."""

    kind: PhraseEventKind
    window: int
    forced: bool = False


class PhraseSegmenter:
    """
    Máquina de dos estados (silencio o voz) que se alimenta ventana a ventana.

    Empieza una frase cuando la probabilidad llega a `threshold`; la termina cuando pasan
    `min_silence_windows` ventanas seguidas por debajo de `neg_threshold` (histéresis).
    Si la frase llega a `max_phrase_windows`, se corta a la fuerza y sigue otra en seguida.
    """

    def __init__(
        self,
        min_silence_windows: int,
        max_phrase_windows: int,
        threshold: float = 0.5,
        neg_threshold: float = 0.35,
    ) -> None:
        self.min_silence_windows = min_silence_windows
        self.max_phrase_windows = max_phrase_windows
        self.threshold = threshold
        self.neg_threshold = neg_threshold
        self.in_speech = False
        self._window = 0
        self._phrase_start = 0
        self._silent_windows = 0

    def push(self, speech_prob: float) -> list[PhraseEvent]:
        """Procesa la probabilidad de la ventana siguiente y devuelve los eventos que provoca."""
        index = self._window
        self._window += 1
        events: list[PhraseEvent] = []
        if not self.in_speech:
            if speech_prob >= self.threshold:
                self._start(index, events)
            return events

        self._silent_windows = self._silent_windows + 1 if speech_prob < self.neg_threshold else 0
        if self._silent_windows >= self.min_silence_windows:
            self.in_speech = False
            events.append(PhraseEvent(PhraseEventKind.END, index + 1))
        elif index + 1 - self._phrase_start >= self.max_phrase_windows:
            events.append(PhraseEvent(PhraseEventKind.END, index + 1, forced=True))
            self._start(index + 1, events)
        return events

    def skip(self, windows: int) -> None:
        """
        Salta ventanas que no se procesan (canal cerrado): queda en silencio y las
        siguientes conservan su número, así los tiempos siguen al audio real.
        """
        self.in_speech = False
        self._silent_windows = 0
        self._window += windows

    def _start(self, window: int, events: list[PhraseEvent]) -> None:
        self.in_speech = True
        self._phrase_start = window
        self._silent_windows = 0
        events.append(PhraseEvent(PhraseEventKind.START, window))
