"""Formato del archivo .md de una transcripción: encabezado y una línea por frase final."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.engine import TranscriptEvent
from core.live_view import LatencySummary

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


def format_latency_line(source: str, summary: LatencySummary) -> str:
    """Por ejemplo "Ellos: mediana 1,8 s, p90 2,4 s (120 frases)", con coma decimal."""
    text = f"mediana {summary.median:.1f} s, p90 {summary.p90:.1f} s".replace(".", ",")
    unit = "frase" if summary.count == 1 else "frases"
    return f"{source_label(source)}: {text} ({summary.count} {unit})"


def format_latency_footer(summaries: dict[str, LatencySummary]) -> str:
    """
    Pie del .md con la latencia final de cada canal (fin de la frase -> texto final).

    Sin frases medidas no hay pie: el archivo queda como antes.
    """
    if not summaries:
        return ""
    lines = [f"- {format_latency_line(source, item)}" for source, item in summaries.items()]
    return "\n## Latencia\n\n" + "\n".join(lines) + "\n"
