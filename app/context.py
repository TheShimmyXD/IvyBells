"""
Contexto del Agente: el contexto con nombre en uso y la foto `contexto.md`.

Un contexto es una carpeta de `resources/agent/contextos/`; se recuerda su nombre en
`app_settings.json`. La foto se rehace al cambiar de contexto y con Recargar (no en cada
envío, para no perder la caché de Claude), en su propio hilo: PDF y Word tardan. En cada
envío se lee `contexto.md` tal como está, así lo que el autor corrija a mano también vale.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.background import Post, call_now, ignore, join, start_task
from domain.agent.agent_context import ContextError
from domain.agent.context_budget import estimate_tokens, path_weights, section_chars
from paths import AGENT_CONTEXT_FILE
from services.service_context import ContextReport, read_context, write_context
from services.service_contexts import ContextStore
from services.service_opener import open_path

logger = logging.getLogger(__name__)

ContextWriter = Callable[[list[str], Path], ContextReport]
Opener = Callable[[Path], None]

# Omitidos que se nombran en el aviso; el resto está en contexto.md.
NOTICE_OMITTED = 3
CLOSE_TIMEOUT_S = 3.0
NEW_NAME = "nuevo contexto"


def describe_report(files: int, chars: int, omitted: list) -> str:
    """Una línea para la puerta: archivos, caracteres y omitidos."""
    thousands = f"{chars:,}".replace(",", ".")
    text = f"contexto.md: {files} archivos, {thousands} caracteres"
    if omitted:
        shown = ", ".join(f"{Path(o.path).name} ({o.reason})" for o in omitted[:NOTICE_OMITTED])
        more = f" y {len(omitted) - NOTICE_OMITTED} más" if len(omitted) > NOTICE_OMITTED else ""
        text += f"; omitidos: {shown}{more}"
    return text


@dataclass
class ContextListeners:
    """
    Avisos del contexto a su dueño, siempre en el hilo dueño. Por defecto no hacen nada.

    changed()      -> cambió la lista de contextos (uno nuevo o renombrado).
    active(str)    -> el contexto en uso, ya guardado ("" = sin contexto).
    reloaded(dict) -> `text` (resumen de la foto o aviso) y `level` ("busy" al empezar;
                      al terminar "ok", "warning", "info" o "error").
    """

    changed: Callable[[], None] = ignore
    active: Callable[[str], None] = ignore
    reloaded: Callable[[dict], None] = ignore


class ContextLibrary:
    """Caso de uso del contexto; se usa desde un solo hilo (el dueño)."""

    def __init__(
        self,
        active: str = "",
        save_active: Callable[[str], object] | None = None,
        target: Path = AGENT_CONTEXT_FILE,
        writer: ContextWriter = write_context,
        store: ContextStore | None = None,
        opener: Opener = open_path,
    ) -> None:
        self.store = store or ContextStore()
        self._active = active
        self._save_active = save_active
        self.target = target
        self._writer = writer
        self._opener = opener
        self.listeners = ContextListeners()
        self._post: Post = call_now
        self._thread: threading.Thread | None = None
        # Recargar mientras se lee: el contexto pudo cambiar, se lee otra vez al terminar.
        self._again = False

    def attach(self, post: Post, listeners: ContextListeners) -> None:
        """Fija el hilo dueño y quién recibe los avisos; la puerta lo llama una vez al armarse."""
        self._post = post
        self.listeners = listeners

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

    # -- Pedidos del dueño -------------------------------------

    def set_active(self, name: str) -> None:
        """Usa el contexto `name` ("" = ninguno) y rehace la foto con él."""
        if (name and name not in self.names()) or name == self.active:
            return
        self._active = name
        if self._save_active is not None:
            self._save_active(name)
        logger.info("Contexto en uso: %s", name or "ninguno")
        self.listeners.active(name)
        self.reload()

    def create(self, name: str = NEW_NAME) -> str:
        """Crea la carpeta, la deja en uso y devuelve su nombre ("" si falló)."""
        try:
            created = self.store.create(name)
        except ContextError as exc:
            self.listeners.reloaded({"text": str(exc), "level": "error"})
            return ""
        self.listeners.changed()
        self.set_active(created)
        return created

    def rename(self, old: str, new: str) -> str:
        """Devuelve el nombre nuevo ("" si falló); el contexto en uso sigue en uso."""
        was_active = old == self.active
        try:
            renamed = self.store.rename(old, new)
        except ContextError as exc:
            self.listeners.reloaded({"text": str(exc), "level": "error"})
            return ""
        self.listeners.changed()
        if was_active and renamed != old:
            # La foto guarda las rutas viejas: se rehace con la carpeta renombrada.
            self.set_active(renamed)
        return renamed

    def open_folder(self) -> bool:
        """Muestra la carpeta del contexto en uso en el explorador; False si no se pudo."""
        if self.folder is None:
            self.listeners.reloaded({"text": "No hay un contexto en uso", "level": "error"})
            return False
        return self._open(self.folder)

    def open_snapshot(self) -> bool:
        """Abre `contexto.md` para revisarlo a mano; False si aún no existe o no se pudo."""
        return self._open(self.target)

    def _open(self, path: Path) -> bool:
        try:
            self._opener(path)
        except OSError as exc:
            self.listeners.reloaded(
                {"text": f"No se pudo abrir {path.name}: {exc}", "level": "error"}
            )
            return False
        return True

    def reload(self) -> None:
        """Rehace la foto del contexto en uso en un hilo; el resumen llega por `reloaded`."""
        if self._thread is not None:
            self._again = True
            return
        self.listeners.reloaded({"text": "Leyendo el contexto...", "level": "busy"})
        paths, target, writer = list(self.paths), self.target, self._writer
        self._thread = start_task(
            lambda: writer(paths, target), self.on_written, self._post, "ivybells-context"
        )

    def close(self, timeout_s: float = CLOSE_TIMEOUT_S) -> None:
        self._again = False
        join(self._thread, timeout_s)

    # -- Aviso del hilo (ya en el hilo dueño) ------------------

    def on_written(self, report: ContextReport | None, error: str) -> None:
        self._thread = None
        if report is None:
            text = f"No se pudo rehacer contexto.md: {error or 'sin respuesta'}"
            self.listeners.reloaded({"text": text, "level": "error"})
        elif not self.paths:
            self.listeners.reloaded(
                {"text": "Sin contexto: el agente responde sin él", "level": "info"}
            )
        else:
            text = describe_report(report.files, report.chars, report.omitted)
            if not report.changed:
                text += " (sin cambios)"
            self.listeners.reloaded({"text": text, "level": "warning" if report.omitted else "ok"})
        if self._again:
            self._again = False
            self.reload()
