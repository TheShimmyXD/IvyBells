from __future__ import annotations

from captura_ui import PreviewCoordinator


def test_theme_button_saves_the_new_theme(qapp):
    from ui._00_ui_main import MainWindow, load_fonts

    saved = []
    window = MainWindow(PreviewCoordinator(), load_fonts(), "dark", saved.append)
    window.theme_button.click()
    window.theme_button.click()
    assert saved == ["light", "dark"]
    window.close()
