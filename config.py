from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.claude_model import ClaudeModelConfig
from core.live_view import SOURCES
from paths import APP_SETTINGS_JSON, LOCAL_SETTINGS_JSON

logger = logging.getLogger(__name__)


# -- Coerción tolerante de valores leídos del JSON -------------


def as_int(value: object, default: int) -> int:
    """Entero > 0 o el valor por defecto."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def as_str(value: object, default: str) -> str:
    """Cadena no vacía o el valor por defecto."""
    text = str(value).strip() if value is not None else ""
    return text or default


# -- Configuración global --------------------------------------

THEME_NAMES = ("light", "dark")
# Módulos de la barra, en su orden.
MODULE_NAMES = ("live", "agent", "config")


@dataclass(slots=True)
class AppConfig:
    """
    Configuración inyectable de la aplicación (fuente única).

    Campos
    ------
    debug : eleva el nivel de log a DEBUG.
    theme : último tema elegido en la ventana (light o dark).
    claude : modelo y opciones de Claude Code (ver core/claude_model.py).
    live_model : modelo de transcripción elegido (la ventana descarta uno desconocido).
    devices : fuente elegida por voz ("ellos", "tu"), por nombre de PipeWire; sin clave
              o vacía = seguir la predeterminada del sistema.
    speaker : interlocutor del módulo Agente ("ellos" o "tu").
    agent_profile : perfil del agente en uso (si ya no existe, se usa el de ejemplo).
    agent_context_paths : archivos y carpetas de contexto del agente, en su orden.
    module : último módulo abierto.

    Las claves faltantes en el JSON toman sus valores por defecto.
    """

    debug: bool = False
    theme: str = "light"
    claude: ClaudeModelConfig = field(default_factory=ClaudeModelConfig)
    live_model: str = "large-v3-turbo"
    devices: dict[str, str] = field(default_factory=dict)
    speaker: str = "ellos"
    agent_profile: str = "ejemplo"
    agent_context_paths: list[str] = field(default_factory=list)
    module: str = "live"

    @classmethod
    def from_dict(cls, data: object) -> AppConfig:
        if not isinstance(data, dict):
            return cls()
        base = cls()
        theme = as_str(data.get("theme"), base.theme)
        speaker = as_str(data.get("speaker"), base.speaker)
        module = as_str(data.get("module"), base.module)
        devices = data.get("devices")
        context = data.get("agent_context_paths")
        return cls(
            debug=bool(data.get("debug", False)),
            theme=theme if theme in THEME_NAMES else base.theme,
            claude=ClaudeModelConfig.from_dict(data.get("claude")),
            live_model=as_str(data.get("live_model"), base.live_model),
            devices={
                source: name.strip()
                for source, name in (devices.items() if isinstance(devices, dict) else ())
                if source in SOURCES and isinstance(name, str) and name.strip()
            },
            speaker=speaker if speaker in SOURCES else base.speaker,
            agent_profile=as_str(data.get("agent_profile"), base.agent_profile),
            agent_context_paths=[
                path.strip()
                for path in (context if isinstance(context, list) else ())
                if isinstance(path, str) and path.strip()
            ],
            module=module if module in MODULE_NAMES else base.module,
        )

    def to_dict(self) -> dict:
        return asdict(self)


# -- Carga y guardado ------------------------------------------


def _read_json(path: Path) -> object:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("No se pudo leer %s: %s", path.name, exc)
    return None


def load_app_config(path: Path | None = None) -> AppConfig:
    """Lee app_settings.json y devuelve un AppConfig (valores por defecto si falla)."""
    return AppConfig.from_dict(_read_json(path or APP_SETTINGS_JSON))


def save_app_config(config: AppConfig, path: Path | None = None) -> bool:
    """Guarda la configuración. Devuelve False si no se pudo escribir."""
    target = path or APP_SETTINGS_JSON
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(config.to_dict(), handle, ensure_ascii=False, indent=2)
        return True
    except OSError as exc:
        logger.error("No se pudo guardar %s: %s", target.name, exc)
        return False


def load_local_settings(path: Path | None = None) -> dict:
    """
    Lee local_settings.json: datos propios de esta máquina.
    Nunca se versiona.
    """
    data = _read_json(path or LOCAL_SETTINGS_JSON)
    return data if isinstance(data, dict) else {}
