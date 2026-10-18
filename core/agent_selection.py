"""
Rango que el autor marca sobre las frases finales de un interlocutor.

El clic izquierdo fija el inicio y el derecho el final, cada uno en una palabra; entra todo
lo de en medio, aunque cruce varias frases. Si el final queda antes que el inicio, se
invierten. Solo se marcan frases finales: el provisional todavía cambia.

El Agente envía mensajes completos (`select_phrases`): desde el inicio de la frase del
primer clic hasta el final de la del segundo. `select_range` recorta por palabra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.live_view import Line

_WORD = re.compile(r"\S+")


@dataclass(frozen=True, slots=True, order=True)
class WordPos:
    """Palabra `word` (desde 0) de la frase final `phrase` (desde 0)."""

    phrase: int
    word: int


@dataclass(frozen=True, slots=True)
class Selection:
    start: WordPos
    end: WordPos
    lines: tuple[Line, ...]

    def text(self) -> str:
        """Una línea por frase, con su hora: "[10:02:13] texto"."""
        return "\n".join(
            f"[{line.clock}] {line.text}" if line.clock else line.text for line in self.lines
        )


def word_at(text: str, offset: int) -> int:
    """Índice de la palabra que contiene `offset` (o la anterior, si cae en un espacio)."""
    index = 0
    for number, match in enumerate(_WORD.finditer(text)):
        if match.start() > offset:
            break
        index = number
    return index


def select_range(lines: list[Line], a: WordPos, b: WordPos) -> Selection | None:
    """
    El fragmento entre dos posiciones, en el orden en que se dijo.

    Devuelve None si no hay frases o si una posición apunta fuera de la lista.
    Una palabra fuera de su frase se ajusta al borde.
    """
    if not lines or not all(0 <= pos.phrase < len(lines) for pos in (a, b)):
        return None
    start, end = (a, b) if a <= b else (b, a)
    picked = []
    for index in range(start.phrase, end.phrase + 1):
        words = lines[index].text.split()
        first = start.word if index == start.phrase else 0
        last = end.word if index == end.phrase else len(words) - 1
        first = min(max(first, 0), max(len(words) - 1, 0))
        last = min(max(last, first), len(words) - 1)
        text = " ".join(words[first : last + 1])
        if text:
            picked.append(Line(lines[index].clock, text))
    if not picked:
        return None
    return Selection(start, end, tuple(picked))


def select_phrases(lines: list[Line], a: WordPos, b: WordPos) -> Selection | None:
    """
    Las frases completas entre dos posiciones, con las intermedias.

    La palabra de cada posición no importa: el rango va desde la primera palabra de la
    frase más temprana hasta la última de la más tardía. Devuelve None como `select_range`.
    """
    if not lines or not all(0 <= pos.phrase < len(lines) for pos in (a, b)):
        return None
    first, last = sorted((a.phrase, b.phrase))
    last_word = max(len(lines[last].text.split()) - 1, 0)
    return select_range(lines, WordPos(first, 0), WordPos(last, last_word))
