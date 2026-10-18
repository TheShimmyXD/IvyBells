"""
Lector de la salida `stream-json` de `claude -p`, línea por línea.

Solo interesan dos cosas: los trozos de texto de la respuesta (`text_delta`) y el
resultado final. El razonamiento (`thinking_delta`) y los demás eventos se ignoran.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class Finished:
    """Fin de la respuesta; si `is_error`, `text` trae el motivo que dio la CLI."""

    text: str
    is_error: bool
    duration_ms: int | None = None
    ttft_ms: int | None = None


StreamUpdate = TextDelta | Finished


def parse_line(line: str) -> StreamUpdate | None:
    """Lo que trae una línea del stream, o None si no es texto ni el resultado."""
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(event, dict):
        return None
    if event.get("type") == "stream_event":
        delta = (event.get("event") or {}).get("delta") or {}
        if delta.get("type") == "text_delta" and delta.get("text"):
            return TextDelta(delta["text"])
        return None
    if event.get("type") == "result":
        is_error = bool(event.get("is_error")) or event.get("subtype") != "success"
        text = event.get("result")
        if not isinstance(text, str):
            text = "; ".join(event.get("errors") or []) or str(event.get("subtype", ""))
        return Finished(text, is_error, event.get("duration_ms"), event.get("ttft_ms"))
    return None
