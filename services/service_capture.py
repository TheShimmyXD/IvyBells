"""
Captura de una fuente de PipeWire con `parec` como subproceso.

La fuente se elige por nombre (`-d`): nunca se cambia la predeterminada del sistema.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Callable

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Tamaño de cada bloque entregado y latencia que se le pide a PipeWire.
BLOCK_S = 0.1
LATENCY_MSEC = 100
BYTES_PER_SAMPLE = 2
STOP_TIMEOUT_S = 2.0

BlockCallback = Callable[[str, np.ndarray], None]


def parec_command(device: str) -> list[str]:
    """Orden de `parec` para leer la fuente en PCM de 16 bits, 16 kHz, mono."""
    return [
        "parec",
        "-d",
        device,
        "--format=s16le",
        f"--rate={SAMPLE_RATE}",
        "--channels=1",
        f"--latency-msec={LATENCY_MSEC}",
    ]


def pcm16_to_float32(data: bytes) -> np.ndarray:
    """PCM s16le a float32 en [-1, 1); un byte suelto al final se descarta."""
    usable = len(data) - len(data) % BYTES_PER_SAMPLE
    return np.frombuffer(data[:usable], dtype="<i2").astype(np.float32) / 32768.0


class AudioCapture:
    """
    Lee una fuente en un hilo propio y entrega bloques de ~100 ms a `on_block(source, samples)`.

    `on_block` corre en el hilo lector: debe ser rápido (por ejemplo, poner en una cola).
    """

    def __init__(
        self,
        source: str,
        device: str,
        on_block: BlockCallback,
        command: list[str] | None = None,
    ) -> None:
        self.source = source
        self.device = device
        self._on_block = on_block
        self._command = command or parec_command(device)
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        # stderr a DEVNULL: si nadie lo lee, su búfer se llena y parec se cuelga.
        # Sesión propia: el Ctrl+C de la terminal no lo mata; lo detiene `stop`.
        self._process = subprocess.Popen(
            self._command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._thread = threading.Thread(
            target=self._read_loop, name=f"capture-{self.source}", daemon=True
        )
        self._thread.start()
        logger.info("Capturando %s desde %s", self.source, self.device)

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=STOP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        if self._thread is not None:
            self._thread.join(timeout=STOP_TIMEOUT_S)

    def _read_loop(self) -> None:
        block_bytes = int(BLOCK_S * SAMPLE_RATE) * BYTES_PER_SAMPLE
        stream = self._process.stdout
        while True:
            data = stream.read(block_bytes)
            if not data:
                break
            samples = pcm16_to_float32(data)
            if len(samples):
                self._on_block(self.source, samples)
        code = self._process.wait()
        if code not in (0, -15):
            logger.error("parec terminó con código %s en %s", code, self.device)
