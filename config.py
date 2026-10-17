from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

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


@dataclass(slots=True)
class AppConfig:
    """
    Configuración inyectable de la aplicación (fuente única).

    Campos
    ------
    debug : eleva el nivel de log a DEBUG.

    Las claves faltantes en el JSON toman sus valores por defecto.
    """

    debug: bool = False

    @classmethod
    def from_dict(cls, data: object) -> AppConfig:
        if not isinstance(data, dict):
            return cls()
        return cls(debug=bool(data.get("debug", False)))

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
