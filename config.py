from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.agent_ahead import AGENT_MODES, MANUAL
from core.chat_prompt import DEFAULT_CHAT_EFFORT, DEFAULT_CHAT_MODEL
from core.claude_model import EFFORT_LEVELS, ClaudeModelConfig, is_valid_model
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
AGENT_PANELS = ("agent", "chat")


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
    agent_mode : modo del Agente ("manual" o "ahead", el anticipado).
    agent_panel : lo que muestra la columna derecha del Agente ("agent" o "chat").
    chat_model, chat_effort : modelo y esfuerzo del chat propio, aparte del agente.
    closed_sources : canales cerrados en Transcripción; nunca los dos.
    agent_profile : perfil del agente en uso (si ya no existe, se usa el de ejemplo).
    agent_context : contexto con nombre en uso, una carpeta de resources/agent/contextos
                    ("" = sin contexto).
    module : último módulo abierto.

    Las claves faltantes en el JSON toman sus valores por defecto.
    """

    debug: bool = False
    theme: str = "light"
    claude: ClaudeModelConfig = field(default_factory=ClaudeModelConfig)
    live_model: str = "large-v3-turbo"
    devices: dict[str, str] = field(default_factory=dict)
    speaker: str = "ellos"
    agent_mode: str = MANUAL
    agent_panel: str = "agent"
    chat_model: str = DEFAULT_CHAT_MODEL
    chat_effort: str = DEFAULT_CHAT_EFFORT
    closed_sources: list[str] = field(default_factory=list)
    agent_profile: str = "ejemplo"
    agent_context: str = ""
    module: str = "live"

    @classmethod
    def from_dict(cls, data: object) -> AppConfig:
        if not isinstance(data, dict):
            return cls()
        base = cls()
        theme = as_str(data.get("theme"), base.theme)
        speaker = as_str(data.get("speaker"), base.speaker)
        agent_mode = as_str(data.get("agent_mode"), base.agent_mode)
        module = as_str(data.get("module"), base.module)
        panel = as_str(data.get("agent_panel"), base.agent_panel)
        chat_model = as_str(data.get("chat_model"), base.chat_model)
        chat_effort = data.get("chat_effort")
        devices = data.get("devices")
        closed = data.get("closed_sources")
        closed = sorted(
            {source for source in (closed if isinstance(closed, list) else ()) if source in SOURCES}
        )
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
            agent_mode=agent_mode if agent_mode in AGENT_MODES else base.agent_mode,
            agent_panel=panel if panel in AGENT_PANELS else base.agent_panel,
            chat_model=chat_model if is_valid_model(chat_model) else base.chat_model,
            chat_effort=chat_effort if chat_effort in EFFORT_LEVELS else base.chat_effort,
            closed_sources=closed if len(closed) < len(SOURCES) else [],
            agent_profile=as_str(data.get("agent_profile"), base.agent_profile),
            agent_context=as_str(data.get("agent_context"), base.agent_context),
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
