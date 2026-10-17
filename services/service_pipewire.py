from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PACTL_TIMEOUT_S = 5


@dataclass(frozen=True, slots=True)
class AudioSource:
    """Una fuente de audio de PipeWire, tal como la lista `pactl list short sources`."""

    index: int
    name: str
    driver: str
    sample_format: str
    state: str

    @property
    def is_monitor(self) -> bool:
        """La fuente `.monitor` copia lo que suena en una salida (parlantes o audífonos)."""
        return self.name.endswith(".monitor")


@dataclass(frozen=True, slots=True)
class CaptureSources:
    """Las dos fuentes que captura IvyBells: lo que suena y el micrófono."""

    monitor: AudioSource | None
    microphone: AudioSource | None


def parse_short_sources(text: str) -> list[AudioSource]:
    """Convierte la salida de `pactl list short sources` en fuentes. Ignora líneas mal formadas."""
    sources: list[AudioSource] = []
    for line in text.splitlines():
        columns = line.split("\t")
        if len(columns) < 5:
            continue
        try:
            index = int(columns[0])
        except ValueError:
            continue
        sources.append(
            AudioSource(
                index=index,
                name=columns[1],
                driver=columns[2],
                sample_format=columns[3],
                state=columns[4],
            )
        )
    return sources


def parse_default_source(info_text: str) -> str | None:
    """Devuelve el nombre de la fuente por defecto que informa `pactl info`."""
    for line in info_text.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "Default Source" and value.strip():
            return value.strip()
    return None


def find_capture_sources(
    sources: list[AudioSource], default_source: str | None = None
) -> CaptureSources:
    """
    Elige la fuente de lo que suena y la del micrófono.

    Para lo que suena se prefiere la `.monitor` que `pactl` marca como por defecto; si no
    hay, la primera `.monitor`. El micrófono es la primera fuente que no es `.monitor`.
    """
    monitors = [source for source in sources if source.is_monitor]
    monitor = next((source for source in monitors if source.name == default_source), None)
    monitor = monitor or (monitors[0] if monitors else None)
    microphone = next((source for source in sources if not source.is_monitor), None)
    return CaptureSources(monitor=monitor, microphone=microphone)


def _run_pactl(*args: str) -> str:
    # LC_ALL=C: las etiquetas de pactl salen siempre en inglés, sin importar el idioma del sistema.
    env = {**os.environ, "LC_ALL": "C"}
    result = subprocess.run(
        ["pactl", *args],
        capture_output=True,
        text=True,
        timeout=PACTL_TIMEOUT_S,
        env=env,
        check=True,
    )
    return result.stdout


def read_capture_sources() -> CaptureSources:
    """Consulta PipeWire y devuelve las fuentes de captura (ambas pueden ser None)."""
    try:
        sources = parse_short_sources(_run_pactl("list", "short", "sources"))
        default_source = parse_default_source(_run_pactl("info"))
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("No se pudo consultar PipeWire con pactl: %s", exc)
        return CaptureSources(monitor=None, microphone=None)
    return find_capture_sources(sources, default_source)
