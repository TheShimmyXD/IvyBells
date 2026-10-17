from __future__ import annotations

from logging_config import setup_logging


def main() -> None:
    setup_logging()
    # Import diferido: el logging queda configurado antes de cargar Qt y los módulos.
    from ui._00_ui_main import run_app

    run_app()


if __name__ == "__main__":
    main()
