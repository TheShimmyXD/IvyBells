"""
Coordinador del contexto del Agente: las rutas que elige el autor y la foto `contexto.md`.

Las rutas se recuerdan en `app_settings.json`. La foto se rehace solo con Recargar (no en
cada envío, para no perder la caché de Claude), en su propio hilo: PDF y Word tardan. En
cada envío se lee `contexto.md` tal como está, así lo que el autor corrija a mano también
vale.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.agent_context import clean_paths
from paths import AGENT_CONTEXT_FILE
from services.service_context import read_context, write_context
from workers.worker_context import ContextWorker, ContextWriter
from workers.worker_runner import start_worker, stop_thread

logger = logging.getLogger(__name__)

# Omitidos que se nombran en el aviso; el resto está en contexto.md.
NOTICE_OMITTED = 3
CLOSE_TIMEOUT_MS = 3_000


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
    reloaded(dict)  -> `text` (resumen de la foto) y `level` ("busy" al empezar; al terminar
                       "ok", "warning", "info" o "error").
    """

    paths_changed = Signal()
    reloaded = Signal(dict)

    def __init__(
        self,
        paths: list[str] | None = None,
        save_paths: Callable[[list[str]], object] | None = None,
        target: Path = AGENT_CONTEXT_FILE,
        parent: QObject | None = None,
        writer: ContextWriter = write_context,
    ) -> None:
        super().__init__(parent)
        self.paths = clean_paths(paths or [])
        self._save_paths = save_paths
        self.target = target
        self._writer = writer
        self._worker: ContextWorker | None = None
        self._thread: QThread | None = None
        # Recargar mientras se lee: las rutas pudieron cambiar, se lee otra vez al terminar.
        self._again = False

    def is_busy(self) -> bool:
        return self._thread is not None

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
        """Rehace la foto de las rutas en un hilo; el resumen llega por `reloaded`."""
        if self._thread is not None:
            self._again = True
            return
        self.reloaded.emit({"text": "Leyendo las rutas...", "level": "busy"})
        worker = self._worker = ContextWorker(
            writer=self._writer, paths=list(self.paths), target=self.target
        )
        self._thread = start_worker(
            self, worker, on_done=self.on_written, on_cleared=self._clear_refs
        )

    def close(self) -> None:
        self._again = False
        stop_thread(self._thread, CLOSE_TIMEOUT_MS)

    # -- Señales del worker ------------------------------------

    @Slot(dict)
    def on_written(self, payload: dict) -> None:
        report = payload["report"]
        if report is None:
            text = f"No se pudo rehacer contexto.md: {payload['error']}"
            self.reloaded.emit({"text": text, "level": "error"})
        elif not self.paths:
            self.reloaded.emit(
                {"text": "Sin rutas: el agente responde sin contexto", "level": "info"}
            )
        else:
            text = describe_report(report.files, report.chars, report.omitted)
            if not report.changed:
                text += " (sin cambios)"
            self.reloaded.emit({"text": text, "level": "warning" if report.omitted else "ok"})

    # -- Internos ----------------------------------------------

    def _clear_refs(self) -> None:
        self._worker = None
        self._thread = None
        if self._again:
            self._again = False
            self.reload()
