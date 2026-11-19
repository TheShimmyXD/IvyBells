"""Worker que rehace la foto `contexto.md` sin congelar la ventana (PDF y Word tardan)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from services.service_context import ContextReport

logger = logging.getLogger(__name__)

ContextWriter = Callable[[list[str], Path], ContextReport]


class ContextWorker(QObject):
    """
    Signals
    -------
    finished(dict) -> siempre al final: `report` (ContextReport o None) y `error` ("" si salió bien).
    """

    finished = Signal(dict)

    def __init__(self, *, writer: ContextWriter, paths: list[str], target: Path) -> None:
        super().__init__()
        self._writer = writer
        self._paths = paths
        self._target = target

    def run(self) -> None:
        payload: dict = {"report": None, "error": "sin respuesta"}
        try:
            payload = {"report": self._writer(self._paths, self._target), "error": ""}
        except Exception as exc:
            # Frontera del hilo: sin esto Recargar se queda deshabilitado para siempre.
            logger.exception("No se pudo rehacer contexto.md")
            payload = {"report": None, "error": str(exc) or type(exc).__name__}
        finally:
            self.finished.emit(payload)
