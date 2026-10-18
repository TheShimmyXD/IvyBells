"""
Estado de una cuenta de Claude Code, leído de `claude auth status --json` (sin Qt ni procesos).

Cada cuenta vive en su propia carpeta de sesión (`CLAUDE_CONFIG_DIR`); la de siempre es
`~/.claude`. Aquí solo se interpreta la salida y se arma el texto para la ventana.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_UNSAFE = re.compile(r"[^a-z0-9@._-]")


@dataclass(frozen=True, slots=True)
class AccountStatus:
    logged_in: bool
    email: str = ""
    plan: str = ""
    config_dir: str = ""
    error: str = ""


def account_slug(email: str) -> str:
    """Nombre de carpeta para la sesión de una cuenta: el correo sin caracteres raros."""
    return _UNSAFE.sub("_", email.strip().lower())


def parse_status(text: str) -> AccountStatus:
    """La salida json de `auth status`; sin sesión, `loggedIn` viene en false."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return AccountStatus(False, error="la CLI no devolvió un estado legible")
    if not isinstance(data, dict):
        return AccountStatus(False, error="la CLI no devolvió un estado legible")
    return AccountStatus(
        logged_in=bool(data.get("loggedIn")),
        email=str(data.get("email") or "").lower(),
        plan=str(data.get("subscriptionType") or ""),
        config_dir=str(data.get("configDirectory") or ""),
    )


def describe(status: AccountStatus, account: str) -> tuple[str, str]:
    """Frase para la ventana y su nivel: "ok", "warning" o "error"."""
    if status.error:
        return f"No se pudo leer la cuenta: {status.error}", "error"
    wanted = account or "la sesión de siempre"
    if not status.logged_in:
        return f"Sin sesión iniciada para {wanted}: inicia sesión con la orden de abajo", "warning"
    if account and status.email != account:
        return f"La sesión es de {status.email}, no de {account}", "warning"
    plan = f" (plan {status.plan})" if status.plan else ""
    return f"Sesión de {status.email}{plan}", "ok"
