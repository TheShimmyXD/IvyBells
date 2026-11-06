from __future__ import annotations

import importlib.util
import logging
import os
import sys
import time
import wave
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Paquetes pip que traen cuBLAS y cuDNN (sin CUDA Toolkit ni sudo).
CUDA_LIB_PACKAGES = ("nvidia.cublas", "nvidia.cudnn")


@dataclass(frozen=True, slots=True)
class Segment:
    """Un tramo transcrito con sus tiempos dentro del audio, en segundos."""

    start: float
    end: float
    text: str


def cuda_library_dirs() -> list[str]:
    """
    Carpetas `lib/` de cuBLAS y cuDNN instaladas por pip en el entorno.

    CTranslate2 las busca con el cargador del sistema, así que deben ir en LD_LIBRARY_PATH
    antes de que arranque el proceso que usa la GPU.
    """
    dirs: list[str] = []
    for package in CUDA_LIB_PACKAGES:
        spec = importlib.util.find_spec(package)
        if spec is None or not spec.submodule_search_locations:
            logger.warning("No está instalado %s; la GPU puede fallar al cargar", package)
            continue
        lib_dir = Path(next(iter(spec.submodule_search_locations))) / "lib"
        if lib_dir.is_dir():
            dirs.append(str(lib_dir))
    return dirs


def reexec_with_cuda_libraries(module: str) -> None:
    """
    Relanza `python -m <module>` con LD_LIBRARY_PATH hacia cuBLAS y cuDNN si aún no está.

    El cargador del sistema lee esa variable solo al arrancar el proceso, por eso no basta
    con ponerla en `os.environ`. Si ya está puesta, no hace nada y el proceso sigue.
    """
    dirs = cuda_library_dirs()
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if not dirs or all(lib_dir in current.split(os.pathsep) for lib_dir in dirs):
        return
    os.execve(sys.executable, [sys.executable, "-m", module, *sys.argv[1:]], reexec_env(dirs))


def reexec_env(dirs: list[str]) -> dict[str, str]:
    """
    Entorno del proceso relanzado: cuBLAS y cuDNN en LD_LIBRARY_PATH y la raíz del proyecto
    en PYTHONPATH, para que `-m <module>` se encuentre aunque se arranque desde otra carpeta
    (el acceso del menú o `python /ruta/main.py`).
    """
    from paths import ROOT

    current = os.environ.get("LD_LIBRARY_PATH", "")
    python_path = os.environ.get("PYTHONPATH", "")
    return {
        **os.environ,
        "LD_LIBRARY_PATH": os.pathsep.join([*dirs, current]).rstrip(os.pathsep),
        "PYTHONPATH": os.pathsep.join([str(ROOT), python_path]).rstrip(os.pathsep),
    }


def engine_versions() -> dict[str, str]:
    """Versiones del motor y de las librerías CUDA de pip, para el registro de cada corrida."""
    versions: dict[str, str] = {}
    for package in ("faster-whisper", "ctranslate2", "nvidia-cublas-cu12", "nvidia-cudnn-cu12"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "no instalado"
    return versions


def load_audio(path: Path):
    """
    Lee un WAV PCM de 16 bits, mono y 16 kHz como float32 en [-1, 1] (numpy).

    No usa `faster_whisper.decode_audio`: con PyAV 19 falla (`metadata_errors`), y las
    grabaciones del proyecto ya salen en este formato.
    """
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"{path.name}: se espera WAV PCM de 16 bits, mono y 16 kHz")
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def load_model(model_name: str, compute_type: str):
    """Carga un modelo de faster-whisper en la GPU. Devuelve el modelo y los segundos que tardó."""
    from faster_whisper import WhisperModel

    started = time.perf_counter()
    model = WhisperModel(model_name, device="cuda", compute_type=compute_type)
    return model, time.perf_counter() - started


def transcribe(model, audio, *, language: str, beam_size: int, vad_filter: bool) -> list[Segment]:
    """
    Transcribe un audio completo y devuelve sus tramos.

    faster-whisper entrega un generador perezoso: el cómputo ocurre al recorrerlo, por eso
    se convierte a lista aquí y el tiempo medido por quien llama incluye todo el trabajo.
    """
    segments, _info = model.transcribe(
        audio, language=language, beam_size=beam_size, vad_filter=vad_filter
    )
    return [Segment(start=seg.start, end=seg.end, text=seg.text.strip()) for seg in segments]
