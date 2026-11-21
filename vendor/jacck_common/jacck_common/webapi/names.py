"""
Nombres que comparten la ventana de Tauri (crate ``jacck_tauri``) y la API de Python.

Cada app tiene un prefijo en mayusculas (``IVYBELLS``, ``VENONA``) y de el salen las
variables de entorno y la linea con que la API anuncia su puerto. El crate de Rust arma los
mismos nombres con el mismo prefijo (``jacck_common/rust/jacck_tauri/src/sidecar.rs``): si
uno cambia, cambia el otro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PREFIX_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*")


@dataclass(frozen=True)
class SidecarNames:
    """Prefijo de la app y los nombres que salen de el."""

    prefix: str

    def __post_init__(self) -> None:
        if not _PREFIX_PATTERN.fullmatch(self.prefix):
            raise ValueError(f"Prefijo no valido: {self.prefix!r} (mayusculas, A-Z0-9_).")

    @property
    def token_env(self) -> str:
        """Token de la sesion que pasa quien lanza la API."""
        return f"{self.prefix}_API_TOKEN"

    @property
    def port_prefix(self) -> str:
        """Inicio de la linea de la salida estandar que anuncia el puerto."""
        return f"{self.prefix}_API_PORT="

    @property
    def watch_stdin_env(self) -> str:
        """Con ``1``, la API se apaga cuando se cierra su entrada estandar."""
        return f"{self.prefix}_API_WATCH_STDIN"

    @property
    def root_env(self) -> str:
        """Raiz del proyecto si no es la de siempre (la lee la ventana)."""
        return f"{self.prefix}_ROOT"

    def port_line(self, port: int) -> str:
        return f"{self.port_prefix}{port}"
