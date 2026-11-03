"""
Contextos con nombre del agente: una carpeta por contexto en `resources/agent/contextos/`.

Cada carpeta guarda los archivos que el autor quiere que lea el agente (texto, PDF, Word);
Git la ignora porque lleva datos propios. Aquí no se borra nada: vaciar o quitar una
carpeta lo hace el autor desde su explorador.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.agent_context import ContextError
from core.agent_profile import ProfileError, clean_name
from paths import AGENT_CONTEXTS_DIR

logger = logging.getLogger(__name__)


class ContextStore:
    def __init__(self, folder: Path = AGENT_CONTEXTS_DIR) -> None:
        self.folder = folder

    def names(self) -> list[str]:
        """Las carpetas de contexto, en orden alfabético."""
        if not self.folder.is_dir():
            return []
        return sorted((path.name for path in self.folder.iterdir() if path.is_dir()), key=str.lower)

    def path(self, name: str) -> Path:
        return self.folder / name

    def entries(self, name: str) -> list[Path]:
        """Lo que hay directamente dentro del contexto (archivos y subcarpetas)."""
        folder = self.path(name)
        if not name or not folder.is_dir():
            return []
        return sorted(folder.iterdir(), key=lambda path: path.name.lower())

    def create(self, name: str) -> str:
        """Crea la carpeta vacía y devuelve el nombre ya limpio."""
        name = _clean(name)
        self._check_free(name)
        try:
            self.path(name).mkdir(parents=True)
        except OSError as exc:
            raise ContextError(f"No se pudo crear el contexto {name}: {exc}") from exc
        logger.info("Contexto %s creado", name)
        return name

    def rename(self, old: str, new: str) -> str:
        new = _clean(new)
        if new == old:
            return new
        if new.lower() != old.lower():
            self._check_free(new)
        try:
            self.path(old).rename(self.path(new))
        except OSError as exc:
            raise ContextError(f"No se pudo renombrar {old}: {exc}") from exc
        logger.info("Contexto %s renombrado a %s", old, new)
        return new

    def _check_free(self, name: str) -> None:
        if name.lower() in {existing.lower() for existing in self.names()}:
            raise ContextError(f"Ya hay un contexto llamado {name}")


def _clean(text: str) -> str:
    try:
        return clean_name(text)
    except ProfileError as exc:
        raise ContextError(str(exc)) from exc
