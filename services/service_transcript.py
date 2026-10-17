"""Escritura del .md de la transcripción: cada frase final se agrega y se vuelca al disco."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from core.engine import TranscriptEvent
from core.transcript_markdown import format_header, format_phrase, transcript_stem

logger = logging.getLogger(__name__)


def free_transcript_path(directory: Path, started: datetime) -> Path:
    """`<fecha>.md` en la carpeta; si ya existe (dos sesiones en el mismo minuto), `_2`, `_3`..."""
    stem = transcript_stem(started)
    path = directory / f"{stem}.md"
    counter = 2
    while path.exists():
        path = directory / f"{stem}_{counter}.md"
        counter += 1
    return path


class TranscriptWriter:
    """Abre el .md con su encabezado y agrega las frases finales a medida que llegan."""

    def __init__(
        self, directory: Path, started: datetime, model: str, devices: dict[str, str]
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.path = free_transcript_path(directory, started)
        self.phrases = 0
        self._started = started
        self._handle = self.path.open("x", encoding="utf-8")
        self._write(format_header(started, model, devices))

    def add(self, event: TranscriptEvent) -> None:
        if not event.is_final:
            return
        self._write(format_phrase(event, self._started))
        self.phrases += 1

    def close(self) -> None:
        self._handle.close()

    def _write(self, text: str) -> None:
        # Flush por frase: si el proceso se corta, lo transcrito ya está en el disco.
        self._handle.write(text)
        self._handle.flush()
