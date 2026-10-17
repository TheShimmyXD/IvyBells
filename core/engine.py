"""Contrato del motor de transcripción en vivo, independiente de Whisper, Qt y la GPU."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    """
    Texto de una frase de una fuente ("ellos" o "tu").

    Un evento provisional trae la hipótesis actual completa (`stable_words` dice cuántas
    palabras iniciales ya no cambian); el final trae la frase cerrada. Los tiempos son
    segundos desde que empezó el flujo de esa fuente.
    """

    source: str
    is_final: bool
    text: str
    start_s: float
    end_s: float
    stable_words: int = 0


EventCallback = Callable[[TranscriptEvent], None]


class TranscriptionEngine(Protocol):
    """Motor en vivo: recibe audio por fuente y avisa con eventos provisionales y finales."""

    def start(self) -> None:
        """Prepara el motor (carga el modelo) antes del primer `feed`."""

    def feed(self, source: str, samples: np.ndarray) -> None:
        """Entrega audio float32 mono de 16 kHz de una fuente, en el orden en que llegó."""

    def stop(self) -> None:
        """Cierra las frases abiertas (emite sus finales) y libera el motor."""
