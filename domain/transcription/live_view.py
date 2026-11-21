"""Lo que muestra la ventana en vivo: el texto por fuente, la latencia y los nombres cortos."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.bench.bench_metrics import median_s, percentile
from domain.transcription.engine import DEFAULT_MODEL, TranscriptEvent

SOURCES = ("ellos", "tu")
# Modelos de la escucha (clave para el motor, nombre en el boton, ayuda); los muestra la
# web. Las medianas salen de bench/resultados.
LIVE_MODELS = (
    ("small", "small", "El más rápido (mediana 0,5 s) pero erra más"),
    ("medium", "medium", "Intermedio (mediana 1,3 s)"),
    (DEFAULT_MODEL, "turbo", "El elegido: mediana 1,8 s y el mejor texto"),
)
# "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor" -> "analog-stereo.monitor".
_ALSA_PREFIX = re.compile(r"^alsa_(input|output)\.(pci-[0-9a-f_]+\.\d+\.)?")


@dataclass(frozen=True, slots=True)
class LatencySummary:
    """Latencia final de un canal en una sesión: frases medidas, mediana y p90, en segundos."""

    count: int
    median: float
    p90: float


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
        # Por fuente: (posición en sus frases finales, hora "HH:MM") de cada reanudación.
        self._resumes: dict[str, list[tuple[int, str]]] = {source: [] for source in SOURCES}

    def reset(self, started: datetime) -> None:
        self._started = started
        for source in SOURCES:
            self._finals[source] = []
            self._partials[source] = None
            self._resumes[source] = []

    def resume(self, started: datetime) -> None:
        """
        Tramo nuevo de la misma apertura: las frases se quedan; solo cambia la hora
        base, porque el motor vuelve a contar desde cero.
        """
        self._started = started
        mark = f"{started:%H:%M}"
        for source in SOURCES:
            self._partials[source] = None
            marks = self._resumes[source]
            position = len(self._finals[source])
            # Dos reanudaciones sin frases en medio: queda solo la última.
            if marks and marks[-1][0] == position:
                marks.pop()
            marks.append((position, mark))

    def apply(self, event: TranscriptEvent) -> None:
        text = event.text.strip()
        line = Line(self.clock(event.start_s), text)
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

    def resume_marks(self, source: str) -> list[tuple[int, str]]:
        """Dónde se reanudó la escucha: antes de qué frase final y a qué hora."""
        return list(self._resumes.get(source, []))

    def clock(self, start_s: float) -> str:
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
        self._by_source: dict[str, list[float]] = {}

    def mark_audio(self, samples: int, now: float) -> None:
        """Se llama con cada bloque capturado; solo el primero fija el origen."""
        if self._origin is None:
            self._origin = now - samples / self._sample_rate

    def add_final(self, end_s: float, now: float, source: str = "") -> float | None:
        if self._origin is None:
            return None
        value = max(now - self._origin - end_s, 0.0)
        self._values.append(value)
        self._by_source.setdefault(source, []).append(value)
        return value

    def summary(self) -> dict[str, LatencySummary]:
        """Mediana y p90 por canal, en el orden de `SOURCES` (los canales sin frases no salen)."""
        order = {source: index for index, source in enumerate(SOURCES)}
        sources = sorted(self._by_source, key=lambda source: order.get(source, len(order)))
        return {
            source: LatencySummary(len(values), median_s(values), percentile(values, 0.9))
            for source in sources
            if (values := self._by_source[source])
        }

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
