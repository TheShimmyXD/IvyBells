"""
Lector de la salida `stream-json` de `claude -p`, línea por línea.

Solo interesan dos cosas: los trozos de texto de la respuesta (`text_delta`) y el
resultado final, con lo que cobró el envío (`usage`) y la ventana del modelo. El
razonamiento (`thinking_delta`) y los demás eventos se ignoran.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class Usage:
    """
    Tokens de entrada de un envío, del `result` de la CLI.

    input_tokens   : todo lo que leyó el modelo (`input_tokens` + `cache_read_input_tokens`
                     + `cache_creation_input_tokens`).
    cached_tokens  : la parte que vino de la caché (`cache_read_input_tokens`).
    context_window : `contextWindow` del modelo que respondió; None si no vino.
    """

    input_tokens: int
    cached_tokens: int
    context_window: int | None = None


@dataclass(frozen=True, slots=True)
class Finished:
    """Fin de la respuesta; si `is_error`, `text` trae el motivo que dio la CLI."""

    text: str
    is_error: bool
    duration_ms: int | None = None
    ttft_ms: int | None = None
    usage: Usage | None = None


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
        return Finished(
            text, is_error, event.get("duration_ms"), event.get("ttft_ms"), parse_usage(event)
        )
    return None


def _count(data: dict, key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) else 0


def parse_usage(result: dict) -> Usage | None:
    """El `usage` de un `result`; None si no trae ningún token de entrada."""
    usage = result.get("usage")
    if not isinstance(usage, dict):
        return None
    cached = _count(usage, "cache_read_input_tokens")
    total = _count(usage, "input_tokens") + cached + _count(usage, "cache_creation_input_tokens")
    if total <= 0:
        return None
    return Usage(total, cached, _context_window(result.get("modelUsage")))


def _context_window(model_usage: object) -> int | None:
    """La ventana del modelo que más leyó (con respaldo puede haber dos)."""
    if not isinstance(model_usage, dict):
        return None
    models = [entry for entry in model_usage.values() if isinstance(entry, dict)]
    models = [entry for entry in models if isinstance(entry.get("contextWindow"), int)]
    if not models:
        return None
    read = max(models, key=lambda e: _count(e, "inputTokens") + _count(e, "cacheReadInputTokens"))
    return read["contextWindow"]
