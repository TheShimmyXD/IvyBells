"""
LocalAgreement-2 sobre listas de palabras (método de UFAL, whisper_streaming).

Mientras dura una frase se re-transcribe su audio cada poco; lo que coincide al inicio de
las dos últimas hipótesis se confirma (ya no cambia) y el resto es provisional.
"""

from __future__ import annotations

import unicodedata


def normalize_word(word: str) -> str:
    """
    Forma de comparar: minúsculas, sin signos y sin tildes ("¿Qué?" y "que" coinciden).

    Whisper alterna a veces la tilde entre pasadas ("como" y "cómo"); sin quitarla, la
    palabra no se confirmaría.
    """
    decomposed = unicodedata.normalize("NFD", word.lower())
    return "".join(char for char in decomposed if char.isalnum())


def common_prefix_len(first: list[str], second: list[str]) -> int:
    """Cuántas palabras iniciales comparten dos hipótesis, comparadas normalizadas."""
    count = 0
    for word_a, word_b in zip(first, second, strict=False):
        if normalize_word(word_a) != normalize_word(word_b):
            break
        count += 1
    return count


class LocalAgreement:
    """
    Confirma palabras de una frase a medida que llegan hipótesis nuevas.

    Las hipótesis son la transcripción completa de la frase desde su inicio, así que lo
    confirmado se alinea por posición: si una hipótesis nueva reescribe el principio, lo
    ya confirmado se conserva (ya se mostró como definitivo).
    """

    def __init__(self) -> None:
        self.committed: list[str] = []
        self._previous: list[str] = []

    def update(self, hypothesis: list[str]) -> tuple[list[str], list[str]]:
        """Recibe una hipótesis y devuelve (palabras recién confirmadas, palabras provisionales)."""
        agreed = common_prefix_len(self._previous, hypothesis)
        newly_committed: list[str] = []
        if agreed > len(self.committed):
            newly_committed = hypothesis[len(self.committed) : agreed]
            self.committed.extend(newly_committed)
        self._previous = hypothesis
        return newly_committed, hypothesis[len(self.committed) :]

    def finish(self, final_hypothesis: list[str]) -> list[str]:
        """Cierra la frase con su última hipótesis: devuelve la frase completa y se reinicia."""
        words = self.committed + final_hypothesis[len(self.committed) :]
        self.committed = []
        self._previous = []
        return words
