"""Lo que muestra la ventana en vivo: el texto por fuente, la latencia y los nombres cortos."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.bench_metrics import median_s
from core.engine import TranscriptEvent

SOURCES = ("ellos", "tu")
# "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor" -> "analog-stereo.monitor".
_ALSA_PREFIX = re.compile(r"^alsa_(input|output)\.(pci-[0-9a-f_]+\.\d+\.)?")


@dataclass(frozen=True, slots=True)
class Line:
    clock: str
    text: str


class LiveTranscript:
    """
    Frases finales y el provisional actual de cada fuente.

    Un provisional reemplaza al anterior de su fuente; el final lo borra y queda en la
    lista. La hora es la de pared en que empezó la frase, como en el `.md`.
    """

    def __init__(self) -> None:
        self._started: datetime | None = None
        self._finals: dict[str, list[Line]] = {source: [] for source in SOURCES}
        self._partials: dict[str, Line | None] = dict.fromkeys(SOURCES)

    def reset(self, started: datetime) -> None:
        self._started = started
        for source in SOURCES:
            self._finals[source] = []
            self._partials[source] = None

    def apply(self, event: TranscriptEvent) -> None:
        text = event.text.strip()
        line = Line(self._clock(event.start_s), text)
        if event.is_final:
            self._partials[event.source] = None
            if text:
                self._finals.setdefault(event.source, []).append(line)
        else:
            self._partials[event.source] = line if text else None

    def finals(self, source: str) -> list[Line]:
        return list(self._finals.get(source, []))

    def partial(self, source: str) -> Line | None:
        return self._partials.get(source)

    def _clock(self, start_s: float) -> str:
        if self._started is None:
            return ""
        return f"{self._started + timedelta(seconds=start_s):%H:%M:%S}"


class LatencyTracker:
    """
    Latencia final como en el banco en vivo: reloj de pared desde que empezó a sonar el
    primer bloque, menos el final de la frase (`end_s`).
    """

    def __init__(self, sample_rate: int = 16_000) -> None:
        self._sample_rate = sample_rate
        self._origin: float | None = None
        self._values: list[float] = []

    def mark_audio(self, samples: int, now: float) -> None:
        """Se llama con cada bloque capturado; solo el primero fija el origen."""
        if self._origin is None:
            self._origin = now - samples / self._sample_rate

    def add_final(self, end_s: float, now: float) -> float | None:
        if self._origin is None:
            return None
        value = max(now - self._origin - end_s, 0.0)
        self._values.append(value)
        return value

    @property
    def last(self) -> float | None:
        return self._values[-1] if self._values else None

    @property
    def median(self) -> float | None:
        return median_s(self._values) if self._values else None


def short_device_name(name: str) -> str:
    """El nombre de PipeWire sin el prefijo de ALSA ni la ranura PCI (el completo, en la ayuda)."""
    return _ALSA_PREFIX.sub("", name) or name


def resolve_device(names: list[str], preferred: str, default: str | None) -> str | None:
    """
    La fuente que se captura: la elegida si está conectada; si no (o si se eligió seguir
    la predeterminada, ""), la predeterminada; si tampoco está, la primera de la lista.
    """
    if preferred and preferred in names:
        return preferred
    if default and default in names:
        return default
    return names[0] if names else None


def format_latency(last: float | None, median: float | None) -> str:
    """Cifras con coma decimal; sin frases todavía, un guion."""
    if last is None or median is None:
        return "Latencia -"
    return f"Latencia {last:.1f} s, mediana {median:.1f} s".replace(".", ",")
