"""
Modo consola: transcribe en vivo lo que suena ("Ellos") y el micrófono ("Tú").

Las frases finales se imprimen con su hora y se guardan en `transcripciones/<fecha>.md`;
el texto provisional se reescribe en la última línea de la terminal. Ctrl+C termina.
La escucha es la misma de la ventana (`app.live.LiveListening`); el hilo principal de la
consola es su hilo dueño y corre los avisos que llegan a una cola.
"""

from __future__ import annotations

import logging
import queue
import shutil
import signal
import sys
import threading
from collections.abc import Callable

from app.live import LiveListeners, LiveListening
from app.wiring import build_live
from domain.transcription.engine import TranscriptEvent
from domain.transcription.live_state import LiveState
from domain.transcription.transcript_markdown import source_label

logger = logging.getLogger(__name__)

# Borra la línea actual de la terminal (el provisional anterior).
CLEAR_LINE = "\r\x1b[2K"
# Cada cuánto se mira Ctrl+C mientras no llega ningún aviso.
POLL_S = 0.1


def _write(text: str) -> None:
    """Salida para el usuario (el log va aparte, por stderr y a logs/)."""
    sys.stdout.write(text)
    sys.stdout.flush()


class ConsolePrinter:
    """Imprime los finales como líneas y el provisional en una línea que se reescribe."""

    def __init__(
        self,
        clock: Callable[[float], str],
        write: Callable[[str], None] = _write,
        interactive: bool | None = None,
    ) -> None:
        self._clock = clock
        self._write = write
        self._interactive = sys.stdout.isatty() if interactive is None else interactive

    def __call__(self, event: TranscriptEvent) -> None:
        label = source_label(event.source)
        if event.is_final:
            prefix = CLEAR_LINE if self._interactive else ""
            self._write(f"{prefix}[{self._clock(event.start_s)}] {label}: {event.text.strip()}\n")
        elif self._interactive:
            width = shutil.get_terminal_size().columns
            line = f"  ... {label}: {event.text.strip()}"
            # Solo los últimos caracteres: lo nuevo está al final de la hipótesis.
            if len(line) > width - 1:
                line = "  ..." + line[-(width - 6) :]
            self._write(f"{CLEAR_LINE}{line}")

    def clear(self) -> None:
        if self._interactive:
            self._write(CLEAR_LINE)


def run_listening(
    listening: LiveListening,
    model: str,
    compute_type: str,
    devices: dict[str, str],
    stop: threading.Event,
    printer: ConsolePrinter | None = None,
) -> int:
    """
    Corre una escucha hasta que `stop` se activa o la escucha falla.

    Devuelve 0 si terminó bien y 1 si se detuvo por una falla.
    """
    tasks: queue.Queue[Callable[[], None]] = queue.Queue()
    printer = printer or ConsolePrinter(listening.transcript.clock)
    failed: list[str] = []

    def on_state(payload: dict) -> None:
        if payload.get("state") is LiveState.ERROR:
            failed.append(payload.get("message", ""))

    listening.attach(tasks.put, LiveListeners(state=on_state, event=printer))
    listening.start(model, devices, compute_type)
    stopping = False
    try:
        while True:
            if stop.is_set() and not stopping:
                stopping = True
                listening.stop()
            try:
                tasks.get(timeout=POLL_S)()
            except queue.Empty:
                # Los avisos se ponen en la cola antes de que el hilo termine.
                if listening.wait(0) and tasks.empty():
                    break
    finally:
        listening.close()
        printer.clear()
    for message in failed:
        logger.error("La escucha se detuvo: %s", message)
    return 1 if failed else 0


def run_cli(model: str, compute_type: str) -> int:
    """Corre la sesión hasta Ctrl+C; devuelve el código de salida del proceso."""
    listening = build_live()
    devices = listening.default_devices()
    if not devices:
        logger.error("PipeWire no dio ninguna fuente de captura")
        return 1
    for source, device in devices.items():
        logger.info("%s: %s", source_label(source), device)

    # faster-whisper anota cada llamada al modelo: en la consola solo estorba.
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop.set())
    logger.info("Transcribiendo en vivo; Ctrl+C para terminar")
    return run_listening(listening, model, compute_type, devices, stop)
