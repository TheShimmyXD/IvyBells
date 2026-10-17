from __future__ import annotations

from pathlib import Path

# Raíz del proyecto: la carpeta donde vive este archivo.
ROOT = Path(__file__).resolve().parent

RESOURCES_DIR = ROOT / "resources" / "json"
APP_SETTINGS_JSON = RESOURCES_DIR / "app_settings.json"
# Datos propios de esta máquina (nunca se versionan).
LOCAL_SETTINGS_JSON = ROOT / "local_settings.json"

LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "ivybells.log"

# Audio y transcripciones reales: nunca se versionan.
RECORDINGS_DIR = ROOT / "grabaciones"
TRANSCRIPTS_DIR = ROOT / "transcripciones"
BENCH_RESULTS_DIR = ROOT / "bench" / "resultados"
