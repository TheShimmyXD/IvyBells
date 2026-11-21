"""Ventana de escritorio: el binario de Tauri compilado en release.

La ruta no se escribe a mano: el nombre sale del ``Cargo.toml`` de
``desktop/src-tauri`` y la carpeta de compilación, del ``target-dir`` de su
``.cargo/config.toml``: en la máquina del autor, la compartida de ``../jacck_common``;
sin ese archivo (otra máquina), ``desktop/src-tauri/target``. El archivo es local y lo
escribe ``install.sh``, que también compila; aquí solo se busca y se abre.

En otra máquina ``install.sh`` copia el binario a ``desktop/bin`` y borra ``target``
(1,2 GB): la ventana solo necesita el binario. Si después se recompila, manda lo
compilado, para que un cambio en ``web/`` no abra la copia vieja.
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
# Copia del binario fuera de target/, junto a src-tauri (desktop/bin); fuera de Git.
INSTALLED_DIR = "bin"
INSTALL_HINT = "Compílala con ./install.sh (o: cd web && npm run tauri build -- --no-bundle)."

ExecFn = Callable[[Path, list[str], Mapping[str, str]], object]


def _read_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def binary_name(src_tauri: Path) -> str:
    """Nombre del paquete de Rust, que es también el del binario y su clase de ventana."""
    return _read_toml(src_tauri / "Cargo.toml")["package"]["name"]


def build_binary(src_tauri: Path) -> Path:
    """Ruta donde Cargo deja el binario de release según ``.cargo/config.toml``."""
    config = src_tauri / ".cargo" / "config.toml"
    target = src_tauri / "target"
    if config.is_file():
        value = _read_toml(config).get("build", {}).get("target-dir")
        if value:
            target = src_tauri / value
    return (target / "release" / binary_name(src_tauri)).resolve()


def installed_binary(src_tauri: Path) -> Path:
    """Ruta de la copia que deja ``install.sh`` en otra máquina (``desktop/bin``)."""
    return (src_tauri.parent / INSTALLED_DIR / binary_name(src_tauri)).resolve()


def release_binary(src_tauri: Path) -> Path:
    """Binario que abre la ventana: el compilado si existe; si no, la copia instalada.

    Sin ninguno de los dos devuelve la ruta de compilación, que es la que nombra el
    aviso de ``open_window``.
    """
    built = build_binary(src_tauri)
    if built.is_file():
        return built
    installed = installed_binary(src_tauri)
    return installed if installed.is_file() else built


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
