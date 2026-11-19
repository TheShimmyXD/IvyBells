# Copiado de vid2aud v1.1.1 (commit d03adf5, core/worker_runner.py).
# RequestSequence vive ahora en app/claude_ask.py.
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QThread


def start_worker(
    parent: QObject,
    worker: QObject,
    *,
    on_done: Callable[[object], None] | None = None,
    on_cleared: Callable[[], None] | None = None,
    done_signal: str = "finished",
) -> QThread:
    """
    Mueve `worker` a un QThread nuevo, conecta el ciclo de vida y lo arranca.

    Parameters
    ----------
    parent      : dueño del hilo (normalmente el coordinador).
    worker      : QObject con un slot `run()` y una señal de fin.
    on_done     : receptor del payload final. Debe ser un método de un QObject
                  del hilo principal (p. ej. del coordinador), no una lambda:
                  así Qt entrega la señal en el hilo principal.
    on_cleared  : se llama cuando el hilo terminó, para limpiar referencias. El
                  dueño guarda el worker hasta entonces: al soltarlo, Python lo
                  borra en el hilo principal.
    done_signal : nombre de la señal que marca el fin del trabajo.

    Returns
    -------
    El QThread ya iniciado.
    """
    home = parent.thread()
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)  # type: ignore[attr-defined]

    finished = getattr(worker, done_signal)
    if on_done is not None:
        finished.connect(on_done)
    finished.connect(thread.quit)
    # Sin deleteLater: el worker vuelve al hilo principal al terminar y lo borra
    # Python cuando el coordinador suelta su referencia (on_cleared). Con
    # deleteLater, el hilo del worker lo borraba mientras el principal soltaba
    # la referencia: se borraba dos veces (segfault o aborto intermitente,
    # pila en QThread -> sendPostedEvents -> QObject::event).
    finished.connect(lambda *_: worker.moveToThread(home), Qt.ConnectionType.DirectConnection)

    thread.finished.connect(thread.deleteLater)
    if on_cleared is not None:
        thread.finished.connect(on_cleared)

    thread.start()
    return thread


def stop_thread(thread: QThread | None, timeout_ms: int = 3_000) -> None:
    """Pide al hilo que termine y espera como máximo `timeout_ms`."""
    if thread is not None and thread.isRunning():
        thread.quit()
        thread.wait(timeout_ms)
