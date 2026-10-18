"""Worker que lee el estado de una cuenta de Claude (`claude auth status`) sin bloquear la ventana."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.claude_account import AccountStatus

logger = logging.getLogger(__name__)

StatusReader = Callable[[str, Path | None], AccountStatus]


class AccountWorker(QObject):
    """
    Signals
    -------
    finished(dict) -> siempre al final: `_request_id` y `status` (AccountStatus).
    """

    finished = Signal(dict)

    def __init__(
        self,
        *,
        reader: StatusReader,
        executable: str,
        config_dir: Path | None,
        request_id: int,
    ) -> None:
        super().__init__()
        self._reader = reader
        self._executable = executable
        self._config_dir = config_dir
        self._request_id = request_id

    def run(self) -> None:
        status = AccountStatus(False, error="sin respuesta")
        try:
            status = self._reader(self._executable, self._config_dir)
        except Exception as exc:
            # Frontera del hilo: sin esto la ventana se queda esperando para siempre.
            logger.exception("No se pudo leer el estado de la cuenta")
            status = AccountStatus(False, error=str(exc) or type(exc).__name__)
        finally:
            self.finished.emit({"_request_id": self._request_id, "status": status})
