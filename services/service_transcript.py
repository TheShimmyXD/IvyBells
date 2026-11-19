"""
Escritura del .md de la transcripción: cada frase final se agrega y se vuelca al disco.

Un mismo escritor dura toda la apertura de la app: el archivo se crea en el primer
tramo y cada Detener e Iniciar posterior sigue en él con su marca "Reanudada".
"""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import TextIO

from domain.transcription.engine import TranscriptEvent
from domain.transcription.transcript_markdown import (
    format_header,
    format_phrase,
    format_resume,
    transcript_stem,
)

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
    """
    El .md de una apertura: encabezado en el primer tramo, marca en los siguientes y las
    frases finales a medida que llegan.

    Lo usan dos hilos (el worker escribe y la ventana copia), así que todo pasa por un lock.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.path: Path | None = None
        self.phrases = 0
        self._started: datetime | None = None
        self._model = ""
        self._devices: dict[str, str] = {}
        self._handle: TextIO | None = None
        self._lock = threading.Lock()

    def begin(self, started: datetime, model: str, devices: dict[str, str]) -> bool:
        """Abre un tramo que empieza en `started`; True si es el primero (archivo nuevo)."""
        with self._lock:
            is_new = self._handle is None
            if is_new:
                self.directory.mkdir(parents=True, exist_ok=True)
                self.path = free_transcript_path(self.directory, started)
                self._handle = self.path.open("x", encoding="utf-8")
                self.phrases = 0
                text = format_header(started, model, devices)
            else:
                text = format_resume(started, model, devices, self._model, self._devices)
            self._started, self._model, self._devices = started, model, dict(devices)
            self._write(text)
            return is_new

    def add(self, event: TranscriptEvent) -> None:
        if not event.is_final or self._started is None:
            return
        with self._lock:
            if self._write(format_phrase(event, self._started)):
                self.phrases += 1

    def end_segment(self, footer: str = "") -> None:
        """Cierra el tramo sin cerrar el archivo; `footer` es la latencia del tramo."""
        if footer:
            with self._lock:
                self._write(footer)

    def close(self, footer: str = "") -> None:
        """Cierra el archivo; `footer` va al final. Un `begin` posterior abre otro archivo."""
        with self._lock:
            if footer:
                self._write(footer)
            if self._handle is not None:
                self._handle.close()
            self._handle = None
            self._started = None

    def copy_to(self, target: Path) -> None:
        """Copia el archivo tal como está ahora, aunque la escucha siga. OSError si falla."""
        with self._lock:
            if self.path is None:
                raise FileNotFoundError("Todavía no hay transcripción")
            shutil.copyfile(self.path, target)

    def _write(self, text: str) -> bool:
        # Flush por frase: si el proceso se corta, lo transcrito ya está en el disco.
        if self._handle is None:
            return False
        self._handle.write(text)
        self._handle.flush()
        return True
