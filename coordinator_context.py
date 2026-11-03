"""
Coordinador del contexto del Agente: el contexto con nombre en uso y la foto `contexto.md`.

Un contexto es una carpeta de `resources/agent/contextos/`; se recuerda su nombre en
`app_settings.json`. La foto se rehace al cambiar de contexto y con Recargar (no en cada
envío, para no perder la caché de Claude), en su propio hilo: PDF y Word tardan. En cada
envío se lee `contexto.md` tal como está, así lo que el autor corrija a mano también vale.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.agent_context import ContextError
from core.context_budget import estimate_tokens, path_weights, section_chars
from paths import AGENT_CONTEXT_FILE
from services.service_context import read_context, write_context
from services.service_contexts import ContextStore
from workers.worker_context import ContextWorker, ContextWriter
from workers.worker_runner import start_worker, stop_thread

logger = logging.getLogger(__name__)

# Omitidos que se nombran en el aviso; el resto está en contexto.md.
NOTICE_OMITTED = 3
CLOSE_TIMEOUT_MS = 3_000
NEW_NAME = "nuevo contexto"


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
    contexts_changed() -> cambió la lista de contextos (uno nuevo o renombrado).
    active_changed(str) -> el contexto en uso, ya guardado ("" = sin contexto).
    reloaded(dict)      -> `text` (resumen de la foto o aviso) y `level` ("busy" al empezar;
                           al terminar "ok", "warning", "info" o "error").
    """

    contexts_changed = Signal()
    active_changed = Signal(str)
    reloaded = Signal(dict)

    def __init__(
        self,
        active: str = "",
        save_active: Callable[[str], object] | None = None,
        target: Path = AGENT_CONTEXT_FILE,
        parent: QObject | None = None,
        writer: ContextWriter = write_context,
        store: ContextStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store or ContextStore()
        self._active = active
        self._save_active = save_active
        self.target = target
        self._writer = writer
        self._worker: ContextWorker | None = None
        self._thread: QThread | None = None
        # Recargar mientras se lee: el contexto pudo cambiar, se lee otra vez al terminar.
        self._again = False

    def is_busy(self) -> bool:
        return self._thread is not None

    def names(self) -> list[str]:
        return self.store.names()

    @property
    def active(self) -> str:
        """El contexto en uso; "" si no hay o si su carpeta ya no está."""
        return self._active if self._active in self.names() else ""

    @property
    def folder(self) -> Path | None:
        return self.store.path(self.active) if self.active else None

    @property
    def paths(self) -> list[str]:
        """Lo que entra a la foto: la carpeta del contexto en uso, o nada."""
        return [str(self.folder)] if self.folder else []

    def text(self) -> str:
        return read_context(self.target)

    def weights(self) -> dict[str, int]:
        """Tokens estimados que aporta cada archivo o subcarpeta del contexto a la foto."""
        sizes = section_chars(self.text())
        entries = [str(path) for path in self.store.entries(self.active)]
        return {
            path: estimate_tokens(chars) for path, chars in path_weights(entries, sizes).items()
        }

    # -- Pedidos de la vista -----------------------------------

    def set_active(self, name: str) -> None:
        """Usa el contexto `name` ("" = ninguno) y rehace la foto con él."""
        if (name and name not in self.names()) or name == self.active:
            return
        self._active = name
        if self._save_active is not None:
            self._save_active(name)
        logger.info("Contexto en uso: %s", name or "ninguno")
        self.active_changed.emit(name)
        self.reload()

    def create(self, name: str = NEW_NAME) -> str:
        """Crea la carpeta, la deja en uso y devuelve su nombre ("" si falló)."""
        try:
            created = self.store.create(name)
        except ContextError as exc:
            self.reloaded.emit({"text": str(exc), "level": "error"})
            return ""
        self.contexts_changed.emit()
        self.set_active(created)
        return created

    def rename(self, old: str, new: str) -> str:
        """Devuelve el nombre nuevo ("" si falló); el contexto en uso sigue en uso."""
        was_active = old == self.active
        try:
            renamed = self.store.rename(old, new)
        except ContextError as exc:
            self.reloaded.emit({"text": str(exc), "level": "error"})
            return ""
        self.contexts_changed.emit()
        if was_active and renamed != old:
            # La foto guarda las rutas viejas: se rehace con la carpeta renombrada.
            self.set_active(renamed)
        return renamed

    def reload(self) -> None:
        """Rehace la foto del contexto en uso en un hilo; el resumen llega por `reloaded`."""
        if self._thread is not None:
            self._again = True
            return
        self.reloaded.emit({"text": "Leyendo el contexto...", "level": "busy"})
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
            self.reloaded.emit({"text": "Sin contexto: el agente responde sin él", "level": "info"})
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
