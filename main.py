from __future__ import annotations

import argparse
import logging

from logging_config import setup_logging

logger = logging.getLogger(__name__)


def list_sources() -> None:
    """Imprime las dos fuentes de captura que encuentra PipeWire."""
    from services.service_pipewire import read_capture_sources

    capture = read_capture_sources()
    logger.info(f"Lo que suena: {capture.monitor.name if capture.monitor else 'no encontrada'}")
    logger.info(
        f"Micrófono:    {capture.microphone.name if capture.microphone else 'no encontrado'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="IvyBells")
    parser.add_argument("--fuentes", action="store_true", help="lista las fuentes de audio y sale")
    args = parser.parse_args()

    setup_logging()
    if args.fuentes:
        list_sources()
        return
    # Import diferido: el logging queda configurado antes de cargar Qt y los módulos.
    from ui._00_ui_main import run_app

    run_app()


if __name__ == "__main__":
    main()
