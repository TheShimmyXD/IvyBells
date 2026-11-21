"""
Corredor de trabajos largos sin Qt (de Venona): lo que un worker con QThread
hace para la ventana, aqui con ``threading`` para la API local.

Un hilo por trabajo y uno a la vez por tipo. La cancelacion es entre pasos: el trabajo
mira ``ctx.cancelled`` y termina por su cuenta (lo ya guardado se queda). Cada trabajo
tiene su ``EventChannel``: ``progress`` mientras corre y ``done``, ``failed`` o
``cancelled`` al final (siempre el ultimo). El id de cada trabajo deja a la interfaz
descartar los eventos de un trabajo que ya no es el suyo.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping
from enum import StrEnum

from jacck_common.webapi.events import Event, EventChannel

logger = logging.getLogger(__name__)

# Trabajos terminados que se recuerdan (para el estado y para retomar el canal).
KEEP_FINISHED = 20


class JobStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UnknownJobError(LookupError):
    """No hay un trabajo con ese id o ese tipo."""


class JobBusyError(RuntimeError):
    """Ya corre un trabajo de ese tipo."""


class JobContext:
    """Lo que el trabajo ve de su corredor: avisar avance y saber si lo cancelaron."""

    def __init__(self, job: _Job) -> None:
        self._job = job

    @property
    def cancelled(self) -> bool:
        return self._job.cancel_requested.is_set()

    def emit(self, data: dict) -> None:
        """Agrega un evento ``progress`` con ``data`` (debe poder ir a JSON)."""
        self._job.channel.emit("progress", data)


JobFn = Callable[[JobContext, dict], dict | None]


class _Job:
    def __init__(self, job_id: str, kind: str) -> None:
        self.id = job_id
        self.kind = kind
        self.channel = EventChannel()
        self.cancel_requested = threading.Event()
        self.thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return not self.channel.closed

    def snapshot(self) -> dict:
        count, last, closed = self.channel.state()
        status = JobStatus(last.kind) if closed and last else JobStatus.RUNNING
        return {
            "id": self.id,
            "kind": self.kind,
            "status": status.value,
            "events": count,
            "last": dict(last.data) if last else {},
            "cancel_requested": self.cancel_requested.is_set(),
        }


class JobRunner:
    """Lanza trabajos por tipo, uno a la vez por tipo, y guarda sus eventos."""

    def __init__(
        self,
        handlers: Mapping[str, JobFn],
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._handlers = dict(handlers)
        self._new_id = new_id
        self._lock = threading.Lock()
        self._jobs: OrderedDict[str, _Job] = OrderedDict()

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def start(self, kind: str, params: dict | None = None) -> dict:
        handler = self._handlers.get(kind)
        if handler is None:
            raise UnknownJobError(kind)
        with self._lock:
            if any(job.kind == kind and job.running for job in self._jobs.values()):
                raise JobBusyError(kind)
            job = _Job(self._new_id(), kind)
            self._jobs[job.id] = job
            self._forget_old()
        job.thread = threading.Thread(
            target=self._run, args=(job, handler, dict(params or {})), daemon=True
        )
        job.thread.start()
        return job.snapshot()

    def snapshot(self, job_id: str) -> dict:
        return self._job(job_id).snapshot()

    def latest(self, kind: str) -> dict | None:
        """El estado del ultimo trabajo de ``kind`` (None si no hubo): la interfaz que se
        abre a mitad de una corrida retoma su canal con este id."""
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.kind == kind]
        return jobs[-1].snapshot() if jobs else None

    def cancel(self, job_id: str) -> dict:
        """Pide parar; el trabajo termina en su siguiente punto de control."""
        job = self._job(job_id)
        running = job.running
        if running:
            job.cancel_requested.set()
        return {**job.snapshot(), "ok": running}

    def events_after(
        self, job_id: str, after: int, timeout: float | None = None
    ) -> tuple[list[Event], bool]:
        """Eventos con numero mayor que ``after``; si no hay, espera hasta ``timeout``.
        El segundo valor dice si el trabajo ya termino (y por tanto no vendran mas)."""
        return self._job(job_id).channel.events_after(after, timeout)

    def wait(self, job_id: str, timeout: float | None = None) -> bool:
        """Espera a que termine (pruebas y cierre); True si ya no corre."""
        thread = self._job(job_id).thread
        if thread is not None:
            thread.join(timeout)
        return thread is None or not thread.is_alive()

    # -- Interno ------------------------------------------------

    def _job(self, job_id: str) -> _Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise UnknownJobError(job_id)
        return job

    def _forget_old(self) -> None:
        finished = [job.id for job in self._jobs.values() if not job.running]
        for job_id in finished[: max(len(finished) - KEEP_FINISHED, 0)]:
            del self._jobs[job_id]

    def _run(self, job: _Job, handler: JobFn, params: dict) -> None:
        try:
            result = handler(JobContext(job), params) or {}
        except Exception as exc:  # el hilo no puede tumbar a la API
            logger.exception("El trabajo %s (%s) fallo", job.kind, job.id)
            job.channel.close(JobStatus.FAILED.value, {"message": f"{type(exc).__name__}: {exc}"})
            return
        status = JobStatus.CANCELLED if job.cancel_requested.is_set() else JobStatus.DONE
        job.channel.close(status.value, result)
