from __future__ import annotations

import argparse
import logging
import sys

from logging_config import setup_logging

logger = logging.getLogger(__name__)


def list_sources() -> None:
    """Muestra en el log las dos fuentes de captura que encuentra PipeWire."""
    from services.service_pipewire import read_capture_sources

    capture = read_capture_sources()
    logger.info("Lo que suena: %s", capture.monitor.name if capture.monitor else "no encontrada")
    logger.info(
        "Micrófono:    %s", capture.microphone.name if capture.microphone else "no encontrado"
    )


def install_launcher() -> None:
    """Deja IvyBells en el menú de aplicaciones con su logo."""
    from paths import DESKTOP_SRC, LOGO_PNG, ROOT
    from services.service_desktop import binary_name
    from services.service_launcher import install_launcher as write_launcher

    python = ROOT / ".venv" / "bin" / "python"
    write_launcher(ROOT, python, LOGO_PNG, window_class=binary_name(DESKTOP_SRC))


def open_desktop_window() -> int:
    """Abre la ventana de Tauri; ella lanza la API (``main.py --api``) por su cuenta."""
    from paths import DESKTOP_SRC, ROOT
    from services.service_desktop import open_window, release_binary

    return open_window(release_binary(DESKTOP_SRC), ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="IvyBells")
    parser.add_argument("--fuentes", action="store_true", help="lista las fuentes de audio y sale")
    parser.add_argument("--cli", action="store_true", help="transcribe en vivo en la consola")
    parser.add_argument("--api", action="store_true", help="API local para la ventana de Tauri")
    parser.add_argument("--model", default="large-v3-turbo", help="modelo de faster-whisper")
    parser.add_argument("--compute-type", default="int8", help="int8, int8_float16 o float16")
    parser.add_argument(
        "--install-launcher", action="store_true", help="crea el acceso en el menú y sale"
    )
    parser.add_argument(
        "--qt", action="store_true", help="abre la ventana de Qt (respaldo hasta su retiro)"
    )
    args = parser.parse_args()

    if args.qt or args.cli or args.api:
        # La GPU necesita LD_LIBRARY_PATH desde el arranque: relanza el proceso si falta.
        from services.service_whisper import reexec_with_cuda_libraries

        reexec_with_cuda_libraries("main")
    setup_logging()
    if args.install_launcher:
        install_launcher()
        return
    if args.fuentes:
        list_sources()
        return
    if args.api:
        from entrypoints.api.run import run_api

        sys.exit(run_api())
    if args.cli:
        from entrypoints.cli.live import run_cli

        sys.exit(run_cli(args.model, args.compute_type))
    if args.qt:
        # Import diferido: el logging queda configurado antes de cargar Qt y los módulos.
        from entrypoints.ui_qt._00_ui_main import run_app

        run_app()
        return
    sys.exit(open_desktop_window())


if __name__ == "__main__":
    main()
