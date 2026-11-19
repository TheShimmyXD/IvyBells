"""
Contexto de la empresa para el Agente: qué archivos entran y cómo se arma `contexto.md`.

Entra texto con una extensión conocida, y PDF y Word (.docx), de los que el servicio
extrae el texto; lo demás (audio, video, modelos, binarios, el resto de Office, claves)
queda listado como omitido con su motivo y nunca se abre. El armado
no lleva fecha ni nada que cambie solo: con los mismos archivos sale el mismo texto, así
el prefijo del system prompt sigue saliendo de la caché.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

MAX_FILE_CHARS = 20_000
MAX_FILES = 300
# Entradas revisadas al recorrer carpetas: una ruta muy grande (el home) no congela nada.
MAX_SCANNED = 5_000

TEXT_SUFFIXES = frozenset(
    {
        ".md", ".txt", ".csv", ".tsv", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg",
        ".xml", ".html", ".htm", ".rst", ".log", ".sql",
        ".py", ".js", ".ts", ".java", ".c", ".h", ".cpp", ".cs", ".go", ".rs", ".sh",
    }
)  # fmt: skip
MEDIA_SUFFIXES = frozenset(
    {
        ".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aac", ".webm",
        ".mp4", ".mkv", ".avi", ".mov",
    }
)  # fmt: skip
MODEL_SUFFIXES = frozenset(
    {".bin", ".safetensors", ".pt", ".pth", ".onnx", ".gguf", ".ckpt", ".npy", ".npz", ".pkl"}
)
# De estos el servicio extrae el texto; el resto de Office sigue fuera.
EXTRACTED_SUFFIXES = frozenset({".pdf", ".docx"})
DOCUMENT_SUFFIXES = frozenset({".doc", ".odt", ".xls", ".xlsx", ".ppt", ".pptx"})
SECRET_SUFFIXES = frozenset({".key", ".pem", ".p12", ".pfx", ".crt"})
SKIP_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__"})

REASON_HIDDEN = "oculto"
REASON_SECRET = "posible clave o credencial"
REASON_MEDIA = "audio o video"
REASON_MODEL = "modelo o binario"
REASON_DOCUMENT = "Office sin lector"
REASON_TYPE = "tipo no incluido"


@dataclass(frozen=True, slots=True)
class ContextFile:
    path: str
    text: str
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class Omitted:
    path: str
    reason: str


def skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def omit_reason(name: str) -> str:
    """Por qué un archivo no entra, solo por su nombre; "" si es texto o documento y entra."""
    suffix = PurePath(name).suffix.lower()
    if name.startswith(".env") or suffix in SECRET_SUFFIXES:
        return REASON_SECRET
    if name.startswith("."):
        return REASON_HIDDEN
    if suffix in MEDIA_SUFFIXES:
        return REASON_MEDIA
    if suffix in MODEL_SUFFIXES:
        return REASON_MODEL
    if suffix in DOCUMENT_SUFFIXES:
        return REASON_DOCUMENT
    return "" if suffix in TEXT_SUFFIXES or suffix in EXTRACTED_SUFFIXES else REASON_TYPE


def clip(text: str, limit: int = MAX_FILE_CHARS) -> tuple[str, bool]:
    """El texto hasta `limit` caracteres y si se cortó."""
    return (text, False) if len(text) <= limit else (text[:limit], True)


def _fence(text: str) -> str:
    """Una cerca de comillas invertidas más larga que cualquiera dentro del texto."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def build_context(files: list[ContextFile], omitted: list[Omitted]) -> str:
    """`contexto.md`: índice, una sección por archivo (por ruta) y los omitidos."""
    files = sorted(files, key=lambda item: item.path)
    omitted = sorted(omitted, key=lambda item: item.path)
    lines = ["# Contexto de la empresa", "", "Archivos incluidos:"]
    lines += [f"- {item.path}" for item in files] or ["- (ninguno)"]
    for item in files:
        fence = _fence(item.text)
        lines += ["", f"## {item.path}", "", fence, item.text.rstrip("\n"), fence]
        if item.truncated:
            lines.append(f"(Recortado a {MAX_FILE_CHARS} caracteres.)")
    if omitted:
        lines += ["", "## Omitidos", ""]
        lines += [f"- {item.path}: {item.reason}" for item in omitted]
    return "\n".join(lines) + "\n"


class ContextError(ValueError):
    """Un pedido sobre los contextos con nombre que no se puede cumplir; va a la ventana."""


def clean_paths(lines: list[str]) -> list[str]:
    """Rutas sin espacios sobrantes, sin vacías ni repetidas, en el orden dado."""
    seen: list[str] = []
    for line in lines:
        path = line.strip()
        if path and path not in seen:
            seen.append(path)
    return seen
