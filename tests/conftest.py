from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Una sola QApplication sin pantalla para todas las pruebas con Qt."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
