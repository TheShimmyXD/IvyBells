"""Formato del archivo .md de una transcripción: encabezado y una línea por frase final."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.engine import TranscriptEvent

# Fuente del motor -> como se muestra al lector.
SOURCE_LABELS = {"ellos": "Ellos", "tu": "Tú"}


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def transcript_stem(started: datetime) -> str:
    """Nombre base del archivo, por ejemplo "2026-10-17_1805"."""
    return started.strftime("%Y-%m-%d_%H%M")


def format_header(started: datetime, model: str, devices: dict[str, str]) -> str:
    """Título con la fecha, el modelo usado y la fuente de PipeWire de cada voz."""
    lines = [f"# Transcripción {started:%Y-%m-%d %H:%M}", "", f"- Modelo: {model}"]
    lines += [f"- {source_label(source)}: `{device}`" for source, device in devices.items()]
    return "\n".join(lines) + "\n\n"


def format_phrase(event: TranscriptEvent, started: datetime) -> str:
    """
    Una frase como línea de lista con la hora de pared en que empezó.

    `event.start_s` cuenta desde que empezó la captura, que es `started`.
    """
    stamp = started + timedelta(seconds=event.start_s)
    return f"- **{stamp:%H:%M:%S} {source_label(event.source)}:** {event.text.strip()}\n"
