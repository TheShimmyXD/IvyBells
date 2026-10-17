"""
Modo consola: transcribe en vivo lo que suena ("Ellos") y el micrófono ("Tú").

Las frases finales se imprimen con su hora y se guardan en `transcripciones/<fecha>.md`;
el texto provisional se reescribe en la última línea de la terminal. Ctrl+C termina.
"""

from __future__ import annotations

import logging
import shutil
import signal
import sys
import threading
from datetime import datetime

from core.engine import EventCallback, TranscriptEvent
from core.transcript_markdown import source_label
from paths import ROOT, TRANSCRIPTS_DIR

logger = logging.getLogger(__name__)

# Borra la línea actual de la terminal (el provisional anterior).
CLEAR_LINE = "\r\x1b[2K"


def _write(text: str) -> None:
    """Salida para el usuario (el log va aparte, por stderr y a logs/)."""
    sys.stdout.write(text)
    sys.stdout.flush()


class _ConsolePrinter:
    """Imprime los finales como líneas y el provisional en una línea que se reescribe."""

    def __init__(self, started: datetime) -> None:
        self._started = started
        self._interactive = sys.stdout.isatty()

    def __call__(self, event: TranscriptEvent) -> None:
        label = source_label(event.source)
        if event.is_final:
            stamp = self._started.timestamp() + event.start_s
            clock = datetime.fromtimestamp(stamp).strftime("%H:%M:%S")
            prefix = CLEAR_LINE if self._interactive else ""
            _write(f"{prefix}[{clock}] {label}: {event.text.strip()}\n")
        elif self._interactive:
            width = shutil.get_terminal_size().columns
            line = f"  ... {label}: {event.text.strip()}"
            # Solo los últimos caracteres: lo nuevo está al final de la hipótesis.
            if len(line) > width - 1:
                line = "  ..." + line[-(width - 6) :]
            _write(f"{CLEAR_LINE}{line}")


def run_cli(model: str, compute_type: str) -> int:
    """Corre la sesión hasta Ctrl+C; devuelve el código de salida del proceso."""
    from services.service_live import LiveSession
    from services.service_pipewire import read_capture_sources
    from services.service_streaming import create_whisper_engine
    from services.service_transcript import TranscriptWriter

    capture = read_capture_sources()
    devices = {}
    if capture.monitor:
        devices["ellos"] = capture.monitor.name
    if capture.microphone:
        devices["tu"] = capture.microphone.name
    if not devices:
        logger.error("PipeWire no dio ninguna fuente de captura")
        return 1
    for source, device in devices.items():
        logger.info("%s: %s", source_label(source), device)

    # El motor se crea antes que el escritor (la hora de inicio es tras cargar el modelo).
    handlers: list[EventCallback] = []

    def dispatch(event: TranscriptEvent) -> None:
        for handler in handlers:
            handler(event)

    engine = create_whisper_engine(dispatch, model, compute_type)
    # faster-whisper anota cada llamada al modelo: en la consola solo estorba.
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logger.info("Cargando %s %s en la GPU...", model, compute_type)
    engine.start()

    started = datetime.now()
    writer = TranscriptWriter(TRANSCRIPTS_DIR, started, f"{model} {compute_type}", devices)
    handlers += [_ConsolePrinter(started), writer.add]

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop.set())
    logger.info("Transcribiendo en vivo; Ctrl+C para terminar")
    try:
        LiveSession(engine, devices).run(stop)
    finally:
        writer.close()
        _write(CLEAR_LINE if sys.stdout.isatty() else "")
        logger.info("%d frases guardadas en %s", writer.phrases, writer.path.relative_to(ROOT))
    return 0
