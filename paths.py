from __future__ import annotations

import tempfile
from pathlib import Path

# Raíz del proyecto: la carpeta donde vive este archivo.
ROOT = Path(__file__).resolve().parent

RESOURCES_DIR = ROOT / "resources" / "json"
# Letras (IBM Plex, OFL) e iconos (Phosphor, MIT) de la interfaz, con sus licencias.
FONTS_DIR = ROOT / "resources" / "fonts"
ICONS_DIR = ROOT / "resources" / "icons"
ICON_FONT = ICONS_DIR / "phosphor-regular.woff2"
ICON_MAP = ICONS_DIR / "phosphor-regular.json"
APP_SETTINGS_JSON = RESOURCES_DIR / "app_settings.json"
# Datos propios de esta máquina (nunca se versionan).
LOCAL_SETTINGS_JSON = ROOT / "local_settings.json"

# Perfiles del agente (rol, tono y datos de la empresa): solo ejemplo.md se versiona.
AGENT_DIR = ROOT / "resources" / "agent"
AGENT_PROFILES_DIR = AGENT_DIR / "perfiles"
# El perfil de la empresa de antes de los perfiles; al arrancar pasa a la carpeta.
AGENT_PROFILE_LOCAL = AGENT_DIR / "perfil_local.md"
# Carpeta vacía fuera del proyecto donde corre la CLI de Claude, para que no descubra
# el CLAUDE.md ni las skills de ninguna carpeta padre.
AGENT_WORKDIR = Path(tempfile.gettempdir()) / "ivybells_agent"
# Una carpeta de sesión de Claude Code por cuenta (CLAUDE_CONFIG_DIR), fuera del proyecto.
CLAUDE_ACCOUNTS_DIR = Path.home() / ".local" / "share" / "ivybells" / "claude"

LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "ivybells.log"

# Audio y transcripciones reales: nunca se versionan.
RECORDINGS_DIR = ROOT / "grabaciones"
TRANSCRIPTS_DIR = ROOT / "transcripciones"
BENCH_RESULTS_DIR = ROOT / "bench" / "resultados"
