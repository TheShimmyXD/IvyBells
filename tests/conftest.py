from __future__ import annotations

import gc
import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """
    Una sola QApplication sin pantalla para todas las pruebas con Qt.

    Al final borra ventanas y objetos Qt mientras la QApplication sigue viva: si se
    dejan para la salida del intérprete, Python los destruye en cualquier orden y el
    proceso puede caerse después de pasar todas las pruebas (SIGSEGV o SIGABRT).
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()
    gc.collect()
    app.processEvents()
