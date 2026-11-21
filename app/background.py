"""
Tareas cortas en segundo plano: corren en su propio hilo y avisan al hilo dueño con `post`.

Las usan los casos de uso que leen algo lento sin congelar la puerta: el estado de la cuenta
de Claude (`claude auth status`) y la foto del contexto (PDF y Word tardan).

Aquí viven también `Post`, `call_now` e `ignore`, que usan todos los casos de uso con hilos.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Entrega una tarea al hilo dueño (en la API, asyncio con call_soon_threadsafe).
Post = Callable[[Callable[[], None]], None]


def call_now(task: Callable[[], None]) -> None:
    """`Post` sin hilo dueño: corre la tarea en el hilo que avisa (pruebas y consola)."""
    task()


def ignore(*_args: object) -> None:
    """Aviso por defecto de los oyentes: no hace nada."""


def start_task[T](
    work: Callable[[], T],
    on_done: Callable[[T | None, str], None],
    post: Post,
    name: str,
) -> threading.Thread:
    """
    Corre `work` en un hilo y entrega `on_done(resultado, error)` con `post`.

    Si `work` lanza, el resultado es None y `error` el motivo en una línea; si no, `error`
    es "". `on_done` llega siempre, para que la puerta no se quede esperando.
    """

    def run() -> None:
        result: T | None = None
        error = ""
        try:
            result = work()
        except Exception as exc:
            # Frontera del hilo: sin esto la puerta se queda esperando para siempre.
            logger.exception("Falló la tarea %s", name)
            error = str(exc) or type(exc).__name__
        post(lambda: on_done(result, error))

    # daemon: cerrar la app no espera a una lectura colgada.
    thread = threading.Thread(target=run, name=name, daemon=True)
    thread.start()
    return thread


def join(thread: threading.Thread | None, timeout_s: float) -> None:
    """Espera a `thread` como máximo `timeout_s`; no hace nada si no hay hilo."""
    if thread is not None and thread.is_alive():
        thread.join(timeout_s)
