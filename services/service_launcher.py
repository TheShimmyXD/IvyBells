"""Acceso de IvyBells en el menú de aplicaciones (formato freedesktop).

Copia el logo a los iconos del usuario y escribe ``IvyBells.desktop``, igual que
vid2aud y Molink. No usa sudo: todo va bajo ``$XDG_DATA_HOME`` (por defecto
``~/.local/share``).
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "IvyBells"
ICON_SUBDIR = Path("icons") / "hicolor" / "256x256" / "apps"
APPLICATIONS_SUBDIR = Path("applications")


def data_home() -> Path:
    """Carpeta de datos del usuario según XDG."""
    value = os.environ.get("XDG_DATA_HOME", "").strip()
    return Path(value) if value else Path.home() / ".local" / "share"


def _quote(path: Path) -> str:
    """Argumento de Exec entre comillas si trae espacios u otros reservados."""
    text = str(path)
    if any(char in text for char in " \t\"'\\$`"):
        escaped = "".join("\\" + c if c in '"`$\\' else c for c in text)
        return f'"{escaped}"'
    return text


def desktop_entry(root: Path, python: Path, icon: Path, window_class: str = APP_NAME) -> str:
    """Contenido de ``IvyBells.desktop`` para la carpeta ``root``.

    ``window_class`` es la clase de la ventana que abre ``main.py`` (la de Tauri se
    llama como su binario): con ella el dock la agrupa bajo este acceso y su logo.
    """
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Version=1.0",
            f"Name={APP_NAME}",
            "GenericName=Transcripción en vivo",
            "Comment=Transcribe en vivo y en la GPU los parlantes y el micrófono, sin nube",
            f"Exec={_quote(python)} {_quote(root / 'main.py')}",
            f"Path={root}",
            f"Icon={icon}",
            "Terminal=false",
            "Categories=AudioVideo;Audio;",
            "Keywords=transcripcion;whisper;audio;llamada;microfono;agente;",
            f"StartupWMClass={window_class}",
            "StartupNotify=true",
            "",
        ]
    )


def install_launcher(
    root: Path,
    python: Path,
    logo_png: Path,
    home: Path | None = None,
    window_class: str = APP_NAME,
) -> Path:
    """Copia el icono, escribe el acceso y devuelve su ruta."""
    base = home or data_home()
    icon = base / ICON_SUBDIR / f"{APP_NAME}.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(logo_png, icon)
    entry = base / APPLICATIONS_SUBDIR / f"{APP_NAME}.desktop"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(desktop_entry(root, python, icon, window_class), encoding="utf-8")
    entry.chmod(0o755)
    logger.info("Acceso en el menú: %s", entry)
    return entry
