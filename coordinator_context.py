"""
Coordinador del contexto del Agente: las rutas que elige el autor y la foto `contexto.md`.

Las rutas se recuerdan en `app_settings.json`. La foto se rehace solo con Recargar (no en
cada envío, para no perder la caché de Claude); en cada envío se lee `contexto.md` tal
como está, así lo que el autor corrija a mano también vale.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.agent_context import clean_paths
from paths import AGENT_CONTEXT_FILE
from services.service_context import read_context, write_context

logger = logging.getLogger(__name__)

# Omitidos que se nombran en el aviso; el resto está en contexto.md.
NOTICE_OMITTED = 3


def describe_report(files: int, chars: int, omitted: list) -> str:
    """Una línea para la ventana: archivos, caracteres y omitidos."""
    thousands = f"{chars:,}".replace(",", ".")
    text = f"contexto.md: {files} archivos, {thousands} caracteres"
    if omitted:
        shown = ", ".join(f"{Path(o.path).name} ({o.reason})" for o in omitted[:NOTICE_OMITTED])
        more = f" y {len(omitted) - NOTICE_OMITTED} más" if len(omitted) > NOTICE_OMITTED else ""
        text += f"; omitidos: {shown}{more}"
    return text


class AgentContext(QObject):
    """
    Signals
    -------
    paths_changed() -> cambió la lista de rutas (ya guardada).
    reloaded(dict)  -> `text` (resumen de la foto) y `level` ("ok", "warning" o "info").
    """

    paths_changed = Signal()
    reloaded = Signal(dict)

    def __init__(
        self,
        paths: list[str] | None = None,
        save_paths: Callable[[list[str]], object] | None = None,
        target: Path = AGENT_CONTEXT_FILE,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.paths = clean_paths(paths or [])
        self._save_paths = save_paths
        self.target = target

    def text(self) -> str:
        return read_context(self.target)

    def set_paths(self, lines: list[str]) -> None:
        paths = clean_paths(lines)
        if paths == self.paths:
            return
        self.paths = paths
        if self._save_paths is not None:
            self._save_paths(list(paths))
        self.paths_changed.emit()

    def add(self, paths: list[str]) -> None:
        self.set_paths([*self.paths, *paths])

    def reload(self) -> None:
        """Rehace la foto de las rutas y avisa el resumen."""
        report = write_context(self.paths, self.target)
        if not self.paths:
            self.reloaded.emit(
                {"text": "Sin rutas: el agente responde sin contexto", "level": "info"}
            )
            return
        text = describe_report(report.files, report.chars, report.omitted)
        if not report.changed:
            text += " (sin cambios)"
        self.reloaded.emit({"text": text, "level": "warning" if report.omitted else "ok"})
