#!/usr/bin/env bash
# Instala IvyBells en Linux: entorno virtual, dependencias y acceso en el menu.
# No usa sudo ni toca el sistema: todo queda en esta carpeta y en ~/.local/share.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' 2>/dev/null; then
    echo "IvyBells necesita Python 3.13 o superior ($PYTHON no sirve)." >&2
    echo "Puedes indicar otro con: PYTHON=python3.13 ./install.sh" >&2
    exit 1
fi

if ! "$PYTHON" -m venv .venv; then
    echo "No se pudo crear el entorno virtual." >&2
    echo "En Debian/Ubuntu/Mint instala el paquete python3-venv y vuelve a intentarlo." >&2
    exit 1
fi

.venv/bin/python -m pip install --upgrade pip
# Solo instala las dependencias de pyproject.toml (cuBLAS y cuDNN incluidos, sin CUDA
# Toolkit); el codigo corre desde esta carpeta.
.venv/bin/python -m pip install .

# API local de la ventana: jacck_common vive al lado de esta carpeta (sin repositorio
# todavia) y se instala antes del extra web, que lo pide.
WINDOW_READY=0
if [ -d ../jacck_common ]; then
    .venv/bin/python -m pip install -e "../jacck_common[webapi]"
    .venv/bin/python -m pip install ".[web]"
    # Ventana de Tauri en release (unos 80 s la primera vez); queda en la carpeta de
    # compilacion compartida de jacck_common. Node y Rust van sin sudo (nvm, rustup).
    if command -v npm >/dev/null && command -v cargo >/dev/null; then
        if (cd web && npm ci && npm run tauri build -- --no-bundle); then
            WINDOW_READY=1
        else
            echo
            echo "Aviso: no se pudo compilar la ventana. Si falta webkit2gtk, instalalo con:"
            echo "  sudo apt install libwebkit2gtk-4.1-dev"
        fi
    else
        echo
        echo "Aviso: faltan npm o cargo para compilar la ventana (Node con nvm, Rust con rustup)."
    fi
else
    echo
    echo "Aviso: no se encontro ../jacck_common; la ventana de Tauri no se puede instalar."
fi

.venv/bin/python main.py --install-launcher

# Lo que no se instala con pip; solo se avisa.
if ! command -v pactl >/dev/null || ! command -v parec >/dev/null; then
    echo
    echo "Aviso: faltan pactl o parec. Instalalos con:"
    echo "  sudo apt install pulseaudio-utils"
fi
if ! command -v nvidia-smi >/dev/null; then
    echo
    echo "Aviso: no se encontro nvidia-smi. El motor necesita una GPU NVIDIA con su driver."
fi
if command -v ldconfig >/dev/null && ! ldconfig -p | grep -q "libxcb-cursor.so.0"; then
    echo
    echo "Aviso: falta libxcb-cursor0. Si la ventana no abre, instalalo con:"
    echo "  sudo apt install libxcb-cursor0"
fi
if ! command -v claude >/dev/null; then
    echo
    echo "Aviso: no se encontro la CLI de Claude Code; el modulo Agente no va a responder."
    echo "La transcripcion funciona sin ella."
fi

echo
if [ "$WINDOW_READY" = 1 ]; then
    echo "Listo. Abre IvyBells desde el menu de aplicaciones o con:"
    echo "  .venv/bin/python main.py"
else
    echo "Sin la ventana de Tauri, por ahora abre la de Qt con:"
    echo "  .venv/bin/python main.py --qt"
fi
echo "La primera vez descarga el modelo de Whisper (unos 1,6 GB) a ~/.cache/huggingface."
