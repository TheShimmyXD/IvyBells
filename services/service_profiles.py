"""
Perfiles del agente guardados como `resources/agent/perfiles/<nombre>.md`.

Solo `ejemplo.md` se versiona; los demás llevan datos de la empresa y Git los ignora.
Listar y leer no escriben nada: mover `perfil_local.md` a la carpeta es un paso aparte
que hace la ventana al arrancar.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core.agent_profile import EXAMPLE_NAME, ProfileError, clean_name, is_editable
from paths import AGENT_PROFILES_DIR

logger = logging.getLogger(__name__)

SUFFIX = ".md"
LEGACY_NAME = "local"


class ProfileStore:
    def __init__(self, folder: Path = AGENT_PROFILES_DIR) -> None:
        self.folder = folder

    def names(self) -> list[str]:
        """Los perfiles, con `ejemplo` primero y los demás en orden alfabético."""
        if not self.folder.is_dir():
            return []
        names = sorted(
            (path.stem for path in self.folder.glob(f"*{SUFFIX}") if path.is_file()),
            key=str.lower,
        )
        if EXAMPLE_NAME in names:
            names.remove(EXAMPLE_NAME)
            names.insert(0, EXAMPLE_NAME)
        return names

    def path(self, name: str) -> Path:
        return self.folder / f"{name}{SUFFIX}"

    def read(self, name: str) -> str:
        try:
            return self.path(name).read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("No se pudo leer el perfil %s: %s", name, exc)
            return ""

    def save(self, name: str, text: str) -> None:
        self._check_editable(name)
        self._write(name, text)

    def create(self, name: str, text: str = "") -> str:
        """Crea un perfil nuevo y devuelve su nombre ya limpio."""
        name = clean_name(name)
        self._check_free(name)
        self._write(name, text)
        return name

    def rename(self, old: str, new: str) -> str:
        self._check_editable(old)
        new = clean_name(new)
        if new == old:
            return new
        if new.lower() != old.lower():
            self._check_free(new)
        try:
            self.path(old).rename(self.path(new))
        except OSError as exc:
            raise ProfileError(f"No se pudo renombrar {old}: {exc}") from exc
        logger.info("Perfil %s renombrado a %s", old, new)
        return new

    def delete(self, name: str) -> None:
        self._check_editable(name)
        try:
            self.path(name).unlink()
        except OSError as exc:
            raise ProfileError(f"No se pudo borrar {name}: {exc}") from exc
        logger.info("Perfil %s borrado", name)

    def adopt_legacy(self, legacy: Path) -> str:
        """
        Pasa `perfil_local.md` (el perfil de antes) a la carpeta como `local`.

        Se mueve, no se copia, para que borrarlo en la ventana no lo traiga de vuelta.
        Devuelve el nombre adoptado o "" si no había nada que mover.
        """
        target = self.path(LEGACY_NAME)
        if not legacy.is_file() or target.exists():
            return ""
        self.folder.mkdir(parents=True, exist_ok=True)
        legacy.rename(target)
        logger.info("%s pasó a ser el perfil %s", legacy.name, LEGACY_NAME)
        return LEGACY_NAME

    # -- Internos ----------------------------------------------

    def _check_editable(self, name: str) -> None:
        if not is_editable(name):
            raise ProfileError(f"El perfil {name} viene con IvyBells: duplícalo para cambiarlo")

    def _check_free(self, name: str) -> None:
        if name.lower() in {existing.lower() for existing in self.names()}:
            raise ProfileError(f"Ya hay un perfil llamado {name}")

    def _write(self, name: str, text: str) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            self.path(name).write_text(text, encoding="utf-8")
        except OSError as exc:
            raise ProfileError(f"No se pudo guardar {name}: {exc}") from exc


def write_if_changed(path: Path, text: str) -> bool:
    """Escribe `text` solo si el archivo no lo tiene ya; True si escribió."""
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    # Temporal y reemplazo: quien lee desde otro hilo nunca ve el archivo a medias.
    partial = path.with_name(path.name + ".tmp")
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)
    return True
