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


@dataclass(frozen=True, slots=True)
class SourceChoices:
    """Todas las fuentes, separadas por tipo, y las que se eligen por defecto."""

    monitors: list[AudioSource]
    inputs: list[AudioSource]
    selected: CaptureSources


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


def parse_info_field(info_text: str, field: str) -> str | None:
    """Devuelve el valor de un campo de `pactl info` (por ejemplo "Default Sink")."""
    for line in info_text.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == field and value.strip():
            return value.strip()
    return None


def find_capture_sources(
    sources: list[AudioSource],
    default_sink: str | None = None,
    default_source: str | None = None,
) -> CaptureSources:
    """
    Elige la fuente de lo que suena y la del micrófono.

    Lo que suena es la `.monitor` de la salida predeterminada (`<default_sink>.monitor`):
    ahí sale el audio de Meet o del navegador. El micrófono es la entrada predeterminada,
    salvo que sea una `.monitor`. Si alguna no aparece, se usa la primera de su tipo y se
    deja un aviso en el log.
    """
    monitors = [source for source in sources if source.is_monitor]
    inputs = [source for source in sources if not source.is_monitor]

    monitor_name = f"{default_sink}.monitor" if default_sink else None
    monitor = next((source for source in monitors if source.name == monitor_name), None)
    if monitor is None and monitors:
        monitor = monitors[0]
        logger.warning("No hay monitor de la salida predeterminada; se usa %s", monitor.name)

    microphone = next((source for source in inputs if source.name == default_source), None)
    if microphone is None and inputs:
        microphone = inputs[0]
        logger.warning("La entrada predeterminada no es un micrófono; se usa %s", microphone.name)
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
    return read_source_choices().selected


def read_source_choices() -> SourceChoices:
    """Consulta PipeWire una vez: las fuentes por tipo y las elegidas por defecto."""
    try:
        sources = parse_short_sources(_run_pactl("list", "short", "sources"))
        info = _run_pactl("info")
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("No se pudo consultar PipeWire con pactl: %s", exc)
        return SourceChoices([], [], CaptureSources(monitor=None, microphone=None))
    selected = find_capture_sources(
        sources,
        default_sink=parse_info_field(info, "Default Sink"),
        default_source=parse_info_field(info, "Default Source"),
    )
    return SourceChoices(
        monitors=[source for source in sources if source.is_monitor],
        inputs=[source for source in sources if not source.is_monitor],
        selected=selected,
    )
