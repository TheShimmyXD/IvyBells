"""
Cuánto de la ventana de Claude ocupa un envío del Agente, por partes.

Las partes son las del envío: reglas y perfil, contexto (system prompt), historial y
fragmento (mensaje). Antes de enviar es una estimación por caracteres, marcada con "~";
después de cada envío vale la cifra real del `usage` de la CLI.

Las constantes salen del banco de contexto con haiku en esfuerzo max
(`bench/resultados/2026-10-17_2040_claude_contexto.json`): sin contexto la CLI cobró 1067
tokens por 1253 caracteres, y cada carácter más costó 1/2,34 de token (con 20 000 y con
80 000 tokens de contexto).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import PurePath

from core.agent_prompt import DEFAULT_MAX_CHARS, Exchange, build_prompt
from core.claude_stream import Usage

CHARS_PER_TOKEN = 2.34
# Lo que la CLI agrega por su cuenta: 1067 - 1253 / 2,34.
CLI_OVERHEAD_TOKENS = 532
# Ventanas medidas (`contextWindow`); otro modelo queda sin medir hasta su primer envío.
MEASURED_WINDOWS = {"haiku": 1_000_000}
# Desde aquí la barra avisa (amarillo) y alerta (rojo).
WARNING_FRACTION = 0.80
ERROR_FRACTION = 0.95

_INDEX_HEADER = "Archivos incluidos:"
_OMITTED_HEADER = "\n## Omitidos\n"


@dataclass(frozen=True, slots=True)
class BudgetPart:
    """Una parte del envío; `limit_chars` es su tope si lo tiene (el historial)."""

    key: str
    label: str
    chars: int
    tokens: int
    limit_chars: int | None = None


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """
    El próximo envío estimado por partes y, si ya hubo uno, lo que cobró de verdad.

    window       : ventana del modelo en uso; None si todavía no se midió.
    last         : `usage` del último envío respondido (None antes del primero).
    first_text_s : segundos al primer texto de ese envío.
    """

    parts: tuple[BudgetPart, ...]
    window: int | None
    last: Usage | None = None
    first_text_s: float | None = None

    @property
    def estimated_tokens(self) -> int:
        return sum(part.tokens for part in self.parts)

    @property
    def fraction(self) -> float | None:
        return self.estimated_tokens / self.window if self.window else None

    @property
    def level(self) -> str:
        """ "ok", "warning" o "error" según cuánto de la ventana ocupa."""
        fraction = self.fraction or 0.0
        if fraction >= ERROR_FRACTION:
            return "error"
        return "warning" if fraction >= WARNING_FRACTION else "ok"

    @property
    def cached_fraction(self) -> float | None:
        """Parte del último envío que vino de la caché."""
        return self.last.cached_tokens / self.last.input_tokens if self.last else None

    def summary(self, short: bool = False) -> str:
        """
        Una línea: "~31,3 k de 1 M tokens (3 %)"; `short` ("~31,3 k de 1 M (3 %)") para
        el pie del Agente.
        """
        amount = f"~{format_tokens(self.estimated_tokens)}"
        if not self.window:
            detail = "" if short else ": se mide en el primer envío"
            return f"{amount} tokens (ventana sin medir{detail})"
        unit = "" if short else " tokens"
        return f"{amount} de {format_tokens(self.window)}{unit} ({format_percent(self.fraction)})"

    def last_summary(self) -> str:
        """La cifra real del último envío, el primer texto y la caché; "" sin envíos."""
        if self.last is None:
            return ""
        text = f"Último envío: {format_tokens(self.last.input_tokens)} tokens"
        if self.first_text_s is not None:
            text += f", primer texto {self.first_text_s:.1f} s".replace(".", ",")
        return f"{text}, {format_percent(self.cached_fraction)} de caché"


def estimate_tokens(chars: int) -> int:
    return round(chars / CHARS_PER_TOKEN) if chars > 0 else 0


def build_budget(
    base_system: str,
    system: str,
    history: list[Exchange],
    fragment: str,
    window: int | None,
    last: Usage | None = None,
    first_text_s: float | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> ContextBudget:
    """
    Parte el envío tal como lo arman `build_system_prompt` y `build_prompt`.

    `base_system` es el system prompt sin contexto (reglas y perfil) y `system`, el
    completo; el costo fijo de la CLI va con las reglas.
    """
    frame = len(build_prompt([], fragment, max_chars))
    full = len(build_prompt(history, fragment, max_chars))
    rules = len(base_system)
    context = max(len(system) - rules, 0)
    parts = (
        BudgetPart("rules", "Reglas y perfil", rules, CLI_OVERHEAD_TOKENS + estimate_tokens(rules)),
        BudgetPart("context", "Contexto", context, estimate_tokens(context)),
        BudgetPart("history", "Historial", full - frame, estimate_tokens(full - frame), max_chars),
        BudgetPart("fragment", "Fragmento", frame, estimate_tokens(frame)),
    )
    return ContextBudget(parts, window, last, first_text_s)


def format_tokens(tokens: int) -> str:
    """532, 31,3 k, 121 k, 1 M, 1,2 M."""
    if tokens < 1_000:
        return str(tokens)
    if tokens < 1_000_000:
        value, unit = tokens / 1_000, "k"
    else:
        value, unit = tokens / 1_000_000, "M"
    text = f"{value:.0f}" if value >= 100 else f"{value:.1f}".removesuffix(".0")
    return f"{text.replace('.', ',')} {unit}"


def format_percent(fraction: float | None) -> str:
    if not fraction:
        return "0 %"
    return "<1 %" if fraction < 0.01 else f"{round(fraction * 100)} %"


def section_chars(context_text: str) -> dict[str, int]:
    """
    Caracteres de cada archivo en `contexto.md`, desde su `## <ruta>` hasta el siguiente.

    Las rutas salen del índice; una sección que el autor borró a mano no cuenta.
    """
    _before, found, rest = context_text.partition(_INDEX_HEADER + "\n")
    if not found:
        return {}
    files = []
    for line in rest.splitlines():
        if not line.startswith("- "):
            break
        files.append(line[2:])
    starts = []
    cursor = 0
    for path in files:
        position = context_text.find(f"\n## {path}\n", cursor)
        if position >= 0:
            starts.append((position, path))
            cursor = position + 1
    end = context_text.find(_OMITTED_HEADER, cursor)
    end = len(context_text) if end < 0 else end
    sizes = {}
    for index, (position, path) in enumerate(starts):
        stop = starts[index + 1][0] if index + 1 < len(starts) else end
        sizes[path] = stop - position
    return sizes


def path_weights(paths: list[str], sizes: dict[str, int]) -> dict[str, int]:
    """Caracteres que aporta cada ruta elegida (archivo o carpeta) a `contexto.md`."""
    weights = {}
    for raw in paths:
        root = str(PurePath(os.path.expanduser(raw)))
        prefix = root.rstrip(os.sep) + os.sep
        weights[raw] = sum(
            size for path, size in sizes.items() if path == root or path.startswith(prefix)
        )
    return weights
