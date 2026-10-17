from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Ventana principal. Por ahora solo muestra el esqueleto de la aplicación."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("IvyBells")
        self.setCentralWidget(QLabel("IvyBells: esqueleto de la aplicación"))
        self.resize(480, 240)


def run_app() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("Ventana principal lista")
    sys.exit(app.exec())
