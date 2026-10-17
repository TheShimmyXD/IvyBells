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


def main() -> None:
    parser = argparse.ArgumentParser(description="IvyBells")
    parser.add_argument("--fuentes", action="store_true", help="lista las fuentes de audio y sale")
    parser.add_argument("--cli", action="store_true", help="transcribe en vivo en la consola")
    parser.add_argument("--model", default="large-v3-turbo", help="modelo de faster-whisper")
    parser.add_argument("--compute-type", default="int8", help="int8, int8_float16 o float16")
    args = parser.parse_args()

    if not args.fuentes:
        # La GPU necesita LD_LIBRARY_PATH desde el arranque: relanza el proceso si falta.
        from services.service_whisper import reexec_with_cuda_libraries

        reexec_with_cuda_libraries("main")
    setup_logging()
    if args.fuentes:
        list_sources()
        return
    if args.cli:
        from cli_live import run_cli

        sys.exit(run_cli(args.model, args.compute_type))
    # Import diferido: el logging queda configurado antes de cargar Qt y los módulos.
    from ui._00_ui_main import run_app

    run_app()


if __name__ == "__main__":
    main()
