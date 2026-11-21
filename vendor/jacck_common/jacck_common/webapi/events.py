"""
Canal de eventos numerados para el SSE (de Venona).

Cada evento lleva un numero (1, 2, 3...) que el SSE manda como ``id:``; con
``Last-Event-ID`` la interfaz retoma donde se corto. El canal se cierra con su ultimo
evento y despues no recibe mas. Sirve igual para un trabajo con fin (``jobs.py``) que
para un flujo largo, como las frases de una escucha en vivo.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """Un aviso: numero, tipo (``event:`` del SSE) y datos que deben poder ir a JSON."""

    seq: int
    kind: str
    data: dict


class ChannelClosedError(RuntimeError):
    """El canal ya dio su ultimo evento."""


class EventChannel:
    """Lista de eventos numerados con espera, segura entre hilos."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._closed = False
        self._changed = threading.Condition()

    def emit(self, kind: str, data: dict) -> Event:
        return self._append(kind, data, close=False)

    def close(self, kind: str, data: dict) -> Event:
        """Agrega el ultimo evento y cierra el canal."""
        return self._append(kind, data, close=True)

    @property
    def closed(self) -> bool:
        with self._changed:
            return self._closed

    def state(self) -> tuple[int, Event | None, bool]:
        """Cuantos eventos hay, el ultimo y si ya se cerro, leidos a la vez."""
        with self._changed:
            last = self._events[-1] if self._events else None
            return len(self._events), last, self._closed

    def events_after(self, after: int, timeout: float | None = None) -> tuple[list[Event], bool]:
        """Eventos con numero mayor que ``after``; si no hay, espera hasta ``timeout``.
        El segundo valor dice si el canal ya se cerro (y por tanto no vendran mas)."""
        with self._changed:
            if len(self._events) <= after and not self._closed:
                self._changed.wait(timeout)
            return list(self._events[max(after, 0) :]), self._closed

    def _append(self, kind: str, data: dict, *, close: bool) -> Event:
        with self._changed:
            if self._closed:
                raise ChannelClosedError(kind)
            event = Event(len(self._events) + 1, kind, dict(data))
            self._events.append(event)
            self._closed = close
            self._changed.notify_all()
            return event
