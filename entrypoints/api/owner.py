"""
El hilo dueño de los casos de uso en la API: su bucle de asyncio.

La escucha, el Agente y el chat entregan sus avisos con `post`; aquí ese `post` es
`call_soon_threadsafe` sobre el bucle de la API, así que su estado solo cambia en el bucle,
donde también corren las rutas `async`. Un middleware fija el bucle en cada petición, antes
de cualquier orden que lance un hilo (la escucha, un envío o el pulso del anticipado).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class LoopOwner:
    """`Post` hacia el bucle de asyncio de la API."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self) -> None:
        """Se llama desde el bucle (un middleware o una ruta `async`)."""
        self._loop = asyncio.get_running_loop()

    def __call__(self, task: Callable[[], None]) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            # La API ya se apagó: el aviso no tiene a quién llegar.
            logger.debug("Aviso sin bucle; se descarta")
            return
        try:
            loop.call_soon_threadsafe(task)
        except RuntimeError:
            logger.debug("El bucle se cerró mientras llegaba un aviso")
