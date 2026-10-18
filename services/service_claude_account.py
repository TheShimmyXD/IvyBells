"""
Cuentas de Claude Code: en qué carpeta de sesión vive cada una y si tiene la sesión iniciada.

Se guarda solo el correo; la carpeta se deriva: si existe la propia de ese correo (se crea
al preparar su inicio de sesión), se usa esa; si no, la de siempre (`~/.claude`, sin
variable). Nunca se leen ni se copian credenciales: el estado sale de `claude auth status`.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from pathlib import Path

from core.claude_account import AccountStatus, account_slug, parse_status
from paths import CLAUDE_ACCOUNTS_DIR

logger = logging.getLogger(__name__)

STATUS_TIMEOUT_S = 15


def config_dir_for(account: str, base: Path = CLAUDE_ACCOUNTS_DIR) -> Path | None:
    """La carpeta de sesión propia de la cuenta, o None para la sesión de siempre."""
    if not account:
        return None
    folder = base / account_slug(account)
    return folder if folder.is_dir() else None


def prepare_account_dir(account: str, base: Path = CLAUDE_ACCOUNTS_DIR) -> Path:
    """Crea la carpeta de sesión de la cuenta (vacía hasta que el autor inicie sesión)."""
    folder = base / account_slug(account)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def claude_env(config_dir: Path | None) -> dict[str, str] | None:
    """Entorno para la CLI con la carpeta de la cuenta; None hereda el de siempre."""
    if config_dir is None:
        return None
    return {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir)}


def read_status(executable: str, config_dir: Path | None) -> AccountStatus:
    """Corre `claude auth status --json` para esa carpeta (sin sesión sale con código 1)."""
    try:
        completed = subprocess.run(
            [executable, "auth", "status", "--json"],
            env=claude_env(config_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=STATUS_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("No se pudo leer el estado de la cuenta: %s", exc)
        return AccountStatus(False, error=f"no se pudo ejecutar '{executable}'")
    status = parse_status(completed.stdout)
    logger.info(
        "Cuenta de Claude: sesión %s, plan %s",
        "iniciada" if status.logged_in else "sin iniciar",
        status.plan or "-",
    )
    return status


def login_command(executable: str, account: str, config_dir: Path | None) -> str:
    """La orden para copiar en una terminal: abre el navegador y pide pegar un código."""
    parts = [executable, "auth", "login"]
    if account:
        parts += ["--email", account]
    line = " ".join(shlex.quote(part) for part in parts)
    if config_dir is None:
        return line
    return f"CLAUDE_CONFIG_DIR={shlex.quote(str(config_dir))} {line}"
