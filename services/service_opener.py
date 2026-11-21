"""
Abre una carpeta o un archivo con la aplicación del sistema (explorador, editor).

La usa la API para los botones de abrir. No espera al
programa que se abre ni cambia nada del sistema: solo lo lanza en su propia sesión, así
cerrar IvyBells no lo cierra.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

logger = logging.getLogger(__name__)

Launcher = Callable[[Sequence[str]], object]


def open_command(path: Path, platform: str = sys.platform) -> list[str]:
    """La orden que abre `path` en este sistema (en Windows se usa `os.startfile`)."""
    if platform == "darwin":
        return ["open", str(path)]
    return ["xdg-open", str(path)]


def _launch(command: Sequence[str]) -> object:
    return subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_path(path: Path, launcher: Launcher = _launch, platform: str = sys.platform) -> None:
    """Abre `path`; levanta OSError si no existe o no se pudo lanzar el programa."""
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    if platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        launcher(open_command(path, platform))
    logger.info("Abierto %s", path)
