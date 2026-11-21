"""Ventana de escritorio: el binario de Tauri compilado en release.

La ruta no se escribe a mano: el nombre sale del ``Cargo.toml`` de
``desktop/src-tauri`` y la carpeta de compilación, del ``target-dir`` de su
``.cargo/config.toml`` (la compartida de ``jacck_common``). ``install.sh`` lo
compila; aquí solo se busca y se abre.
"""

from __future__ import annotations

import logging
import os
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

# El binario lee la raíz del proyecto de esta variable (crate jacck_tauri:
# "<PREFIJO>_ROOT"); sin ella usa la ruta fija al compilar.
ROOT_ENV = "IVYBELLS_ROOT"
INSTALL_HINT = "Compílala con ./install.sh (o: cd web && npm run tauri build -- --no-bundle)."

ExecFn = Callable[[Path, list[str], Mapping[str, str]], object]


def _read_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def binary_name(src_tauri: Path) -> str:
    """Nombre del paquete de Rust, que es también el del binario y su clase de ventana."""
    return _read_toml(src_tauri / "Cargo.toml")["package"]["name"]


def release_binary(src_tauri: Path) -> Path:
    """Ruta del binario de release según ``Cargo.toml`` y ``.cargo/config.toml``."""
    config = src_tauri / ".cargo" / "config.toml"
    target = src_tauri / "target"
    if config.is_file():
        value = _read_toml(config).get("build", {}).get("target-dir")
        if value:
            target = src_tauri / value
    return (target / "release" / binary_name(src_tauri)).resolve()


def open_window(
    binary: Path, root: Path, exec_fn: ExecFn = os.execve, env: Mapping[str, str] | None = None
) -> int:
    """Reemplaza este proceso por la ventana; devuelve 1 si el binario no existe.

    Con ``execve`` no queda un Python esperando detrás de la ventana: la API la
    lanza el propio binario (``main.py --api``) y se apaga al cerrarla.
    """
    if not binary.is_file():
        logger.error("No está compilada la ventana de IvyBells: falta %s", binary)
        logger.error(INSTALL_HINT)
        return 1
    child_env = dict(os.environ if env is None else env)
    child_env[ROOT_ENV] = str(root)
    logger.info("Abriendo la ventana: %s", binary)
    exec_fn(binary, [str(binary)], child_env)
    return 0
