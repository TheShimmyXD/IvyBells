"""
Worker del módulo Agente: envía un turno a Claude y entrega la respuesta por partes.

Corre en su propio QThread; la UI nunca espera a la CLI.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal

from services.service_claude import ClaudeCancelled, ClaudeError, ClaudeService

logger = logging.getLogger(__name__)


class AgentWorker(QObject):
    """
    Signals
    -------
    text(str)      -> un trozo de la respuesta, en cuanto llega.
    failed(str)    -> motivo de la falla, en una línea.
    finished(dict) -> siempre al final: `_request_id`, `answer` y `cancelled`.
    """

    text = Signal(str)
    failed = Signal(str)
    finished = Signal(dict)

    def __init__(
        self,
        *,
        service: ClaudeService,
        prompt: str,
        cancel_event: threading.Event,
        request_id: int,
    ) -> None:
        super().__init__()
        self._service = service
        self._prompt = prompt
        self._cancel = cancel_event
        self._request_id = request_id

    def run(self) -> None:
        answer = ""
        cancelled = False
        try:
            answer = self._service.ask(self._prompt, self.text.emit, self._cancel).text
        except ClaudeCancelled:
            cancelled = True
            logger.info("Envío a Claude cancelado")
        except ClaudeError as exc:
            logger.warning("Claude falló: %s", exc)
            self.failed.emit(str(exc))
        except Exception as exc:
            # Frontera del hilo: sin esto la UI se queda esperando para siempre.
            logger.exception("El envío a Claude falló")
            self.failed.emit(str(exc) or type(exc).__name__)
        finally:
            self.finished.emit(
                {"_request_id": self._request_id, "answer": answer, "cancelled": cancelled}
            )
