from __future__ import annotations

import logging
import subprocess
import threading

logger = logging.getLogger(__name__)

NVIDIA_SMI_TIMEOUT_S = 5
SAMPLE_PERIOD_S = 0.2


def _query_gpu(field: str) -> str:
    result = subprocess.run(
        ["nvidia-smi", f"--query-gpu={field}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=NVIDIA_SMI_TIMEOUT_S,
        check=True,
    )
    # Con una sola GPU la salida es una línea; se toma la primera por si hubiera más.
    return result.stdout.strip().splitlines()[0].strip()


def memory_used_mib() -> int:
    """VRAM ocupada ahora mismo en la GPU 0, en MiB, según nvidia-smi."""
    return int(_query_gpu("memory.used"))


def gpu_identity() -> dict[str, str]:
    """Nombre de la GPU y versión del driver, para fechar cada corrida del banco."""
    try:
        return {"gpu": _query_gpu("name"), "driver": _query_gpu("driver_version")}
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        logger.error("No se pudo consultar nvidia-smi: %s", exc)
        return {"gpu": "desconocida", "driver": "desconocido"}


class VramSampler:
    """
    Muestrea la VRAM ocupada en un hilo mientras corre un bloque `with`.

    Las muestras quedan en `samples_mib`; el pico propio de la corrida se calcula
    restando la línea base medida antes de cargar el modelo.
    """

    def __init__(self, period_s: float = SAMPLE_PERIOD_S) -> None:
        self.period_s = period_s
        self.samples_mib: list[int] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="vram-sampler", daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.samples_mib.append(memory_used_mib())
            except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
                logger.warning("Muestra de VRAM perdida: %s", exc)
            self._stop.wait(self.period_s)

    def __enter__(self) -> VramSampler:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._stop.set()
        self._thread.join()
