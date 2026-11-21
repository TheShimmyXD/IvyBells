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

# API local de la ventana: jacck_common no se publica. Si esta al lado (maquina del
# autor) se usa esa, editable, con la compilacion compartida; si no, la copia de vendor/.
# Va antes del extra web, que lo pide.
WINDOW_READY=0
if [ -d ../jacck_common ]; then
    .venv/bin/python -m pip install -e "../jacck_common[webapi]"
    CARGO_CONFIG=desktop/src-tauri/.cargo/config.toml
    if [ ! -f "$CARGO_CONFIG" ]; then
        mkdir -p "$(dirname "$CARGO_CONFIG")"
        cat > "$CARGO_CONFIG" <<'TOML'
# Compilacion compartida de Tauri en ../jacck_common/rust/target. Archivo local, fuera de
# Git: lo escribe install.sh solo si existe ../jacck_common.
# La ruta es relativa a desktop/src-tauri (la carpeta que contiene .cargo/).
[build]
target-dir = "../../../jacck_common/rust/target"
TOML
    fi
else
    .venv/bin/python -m pip install "./vendor/jacck_common[webapi]"
fi
.venv/bin/python -m pip install ".[web]"
# Ventana de Tauri en release (unos 80 s la primera vez). Node y Rust van sin sudo (nvm,
# rustup).
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
    echo "Sin la ventana de Tauri: resuelve el aviso de arriba y vuelve a correr ./install.sh."
    echo "Mientras tanto se transcribe en la consola con:"
    echo "  .venv/bin/python main.py --cli"
fi
echo "La primera vez descarga el modelo de Whisper (unos 1,6 GB) a ~/.cache/huggingface."
