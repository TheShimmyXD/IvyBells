"""
Lectura de las rutas de contexto del Agente y escritura de `contexto.md`.

IvyBells lee los archivos, no Claude. Se decide por el nombre antes de abrir nada: un
audio, un modelo o un binario nunca se abre. Un texto que no es UTF-8 o trae bytes nulos
queda omitido. `contexto.md` es una foto: solo se reescribe si cambió.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from core.agent_context import (
    MAX_FILE_CHARS,
    MAX_FILES,
    MAX_SCANNED,
    ContextFile,
    Omitted,
    build_context,
    clip,
    omit_reason,
    skip_dir,
)
from paths import AGENT_CONTEXT_FILE
from services.service_profiles import write_if_changed

logger = logging.getLogger(__name__)

# Bytes que se leen como máximo: el tope en caracteres más margen para UTF-8.
_MAX_READ_BYTES = MAX_FILE_CHARS * 4 + 4


@dataclass(frozen=True, slots=True)
class ContextReport:
    files: int
    chars: int
    omitted: list[Omitted]
    changed: bool


def _candidates(root: Path, omitted: list[Omitted]) -> list[Path]:
    """Los archivos de una ruta (archivo o carpeta), en orden estable."""
    if root.is_file():
        return [root]
    if not root.is_dir():
        omitted.append(Omitted(str(root), "no existe"))
        return []
    found: list[Path] = []
    scanned = 0
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(name for name in dirs if not skip_dir(name))
        for name in sorted(names):
            scanned += 1
            if scanned > MAX_SCANNED:
                omitted.append(Omitted(str(root), f"se revisaron {MAX_SCANNED} entradas"))
                return found
            found.append(Path(folder) / name)
    return found


def _read(path: Path) -> tuple[str, bool] | str:
    """(texto, recortado) o el motivo por el que no se pudo leer."""
    try:
        with path.open("rb") as handle:
            data = handle.read(_MAX_READ_BYTES)
    except OSError as exc:
        return f"no se pudo leer ({exc.strerror or exc})"
    if b"\0" in data:
        return "binario"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Si la lectura llegó al tope, una letra cortada en los últimos bytes no es error.
        cut = len(data) == _MAX_READ_BYTES and exc.start >= len(data) - 3
        if not cut:
            return "no es UTF-8"
        text = data[: exc.start].decode("utf-8")
    return clip(text)


def collect(paths: list[str]) -> tuple[list[ContextFile], list[Omitted]]:
    files: list[ContextFile] = []
    omitted: list[Omitted] = []
    seen: set[Path] = set()
    for raw in paths:
        for path in _candidates(Path(raw).expanduser(), omitted):
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            reason = omit_reason(path.name)
            if not reason and len(files) >= MAX_FILES:
                reason = f"se pasó del tope de {MAX_FILES} archivos"
            if reason:
                omitted.append(Omitted(str(path), reason))
                continue
            result = _read(path)
            if isinstance(result, str):
                omitted.append(Omitted(str(path), result))
            else:
                files.append(ContextFile(str(path), *result))
    return files, omitted


def write_context(paths: list[str], target: Path = AGENT_CONTEXT_FILE) -> ContextReport:
    """Rehace la foto de las rutas; sin rutas, `contexto.md` queda vacío."""
    files, omitted = collect(paths)
    text = build_context(files, omitted) if paths else ""
    changed = write_if_changed(target, text)
    logger.info(
        "Contexto: %d archivos, %d caracteres, %d omitidos%s",
        len(files),
        len(text),
        len(omitted),
        "" if changed else " (sin cambios)",
    )
    return ContextReport(len(files), len(text), omitted, changed)


def read_context(target: Path = AGENT_CONTEXT_FILE) -> str:
    try:
        return target.read_text(encoding="utf-8") if target.is_file() else ""
    except OSError as exc:
        logger.warning("No se pudo leer %s: %s", target.name, exc)
        return ""
