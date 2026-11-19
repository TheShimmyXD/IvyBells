"""
Adaptador Qt del contexto del Agente (`app.context.ContextLibrary`).

La vista solo habla con él. La orquestación vive en `app/`; aquí se pasan los avisos del
hilo que rehace la foto al hilo de la ventana y se convierten en señales.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.context import NEW_NAME, ContextLibrary, ContextListeners, ContextWriter
from paths import AGENT_CONTEXT_FILE

__all__ = ["NEW_NAME", "AgentContext"]


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
    # Tarea que llega del hilo de la foto: Qt la pone en cola y la corre en este hilo.
    _posted = Signal(object)

    def __init__(
        self,
        active: str = "",
        save_active: Callable[[str], object] | None = None,
        target: Path = AGENT_CONTEXT_FILE,
        parent: QObject | None = None,
        writer: ContextWriter | None = None,
        store: object | None = None,
        *,
        library: ContextLibrary | None = None,
    ) -> None:
        super().__init__(parent)
        if library is None:
            extra = {"writer": writer} if writer is not None else {}
            library = ContextLibrary(active, save_active, target, store=store, **extra)  # type: ignore[arg-type]
        self.library = library
        self._posted.connect(self._run_posted)
        library.attach(
            self._posted.emit,
            ContextListeners(
                changed=self.contexts_changed.emit,
                active=self.active_changed.emit,
                reloaded=self.reloaded.emit,
            ),
        )

    # -- Lo que lee la vista -----------------------------------

    @property
    def store(self):
        return self.library.store

    @property
    def target(self) -> Path:
        return self.library.target

    def is_busy(self) -> bool:
        return self.library.is_busy()

    def names(self) -> list[str]:
        return self.library.names()

    @property
    def active(self) -> str:
        return self.library.active

    @property
    def folder(self) -> Path | None:
        return self.library.folder

    @property
    def paths(self) -> list[str]:
        return self.library.paths

    def text(self) -> str:
        return self.library.text()

    def weights(self) -> dict[str, int]:
        return self.library.weights()

    # -- Pedidos de la vista -----------------------------------

    def set_active(self, name: str) -> None:
        self.library.set_active(name)

    def create(self, name: str = NEW_NAME) -> str:
        return self.library.create(name)

    def rename(self, old: str, new: str) -> str:
        return self.library.rename(old, new)

    def reload(self) -> None:
        self.library.reload()

    def close(self) -> None:
        self.library.close()

    # -- Internos ----------------------------------------------

    @Slot(object)
    def _run_posted(self, task: Callable[[], None]) -> None:
        task()
