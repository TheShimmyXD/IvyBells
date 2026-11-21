"""
Reglas de acceso de una API local (de Venona).

- Solo ``127.0.0.1``: el socket se abre ahi (``serve.py``) y el ``Host`` debe ser local.
- Un ``Origin`` que no sea la ventana de Tauri o el Vite de desarrollo -> 403, antes de
  mirar el token: una pagina cualquiera del navegador no llega ni a probar.
- Sin ``Authorization: Bearer <token>`` o con otro token -> 401. El token cambia en cada
  arranque y nunca va en la URL (no termina en registros ni en el historial).
"""

from __future__ import annotations

import hmac
import secrets

LOCAL_HOST = "127.0.0.1"
ALLOWED_HOSTS = (LOCAL_HOST, "localhost")
VITE_DEV_PORT = 5173
# Tauri 2 en Linux sirve la interfaz como tauri://localhost (Windows: http://tauri.localhost).
TAURI_ORIGINS = ("tauri://localhost", "http://tauri.localhost")

NO_TOKEN_MESSAGE = "Falta el token de esta sesión o no es el correcto."
BAD_ORIGIN_MESSAGE = "Origen no permitido."


def allowed_origins(vite_port: int = VITE_DEV_PORT) -> tuple[str, ...]:
    """La ventana de Tauri y el Vite de desarrollo, que escucha solo en local."""
    return (
        *TAURI_ORIGINS,
        f"http://{LOCAL_HOST}:{vite_port}",
        f"http://localhost:{vite_port}",
    )


ALLOWED_ORIGINS = allowed_origins()


def new_token() -> str:
    """Token de un arranque: 256 bits al azar."""
    return secrets.token_urlsafe(32)


def origin_allowed(origin: str | None, allowed: tuple[str, ...] = ALLOWED_ORIGINS) -> bool:
    """Sin cabecera ``Origin`` (Tauri en algunas peticiones, pruebas) pasa; el token decide."""
    return origin is None or origin in allowed


def token_matches(authorization: str | None, token: str) -> bool:
    """Compara en tiempo constante ``Bearer <token>`` con el de la sesion."""
    if not authorization or not token:
        return False
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(value.strip().encode(), token.encode())
