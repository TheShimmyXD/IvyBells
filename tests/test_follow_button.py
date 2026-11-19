from __future__ import annotations


def test_floating_button_appears_away_from_the_end_and_follow_brings_it_back(qapp):
    from PySide6.QtWidgets import QTextBrowser

    from entrypoints.ui_qt.blocks.follow_button import MARGIN_PX, FollowButton, is_at_bottom

    browser = QTextBrowser()
    browser.resize(400, 300)
    button = FollowButton(browser)
    browser.show()
    browser.setPlainText("\n".join(f"Frase de ejemplo {index}" for index in range(80)))
    bar = browser.verticalScrollBar()
    bar.setValue(bar.maximum())
    qapp.processEvents()
    assert button.isHidden()
    bar.setValue(0)
    qapp.processEvents()
    assert not button.isHidden()
    # Translúcido y en la esquina inferior derecha del texto, a la izquierda de la barra.
    assert not button.solid
    view = browser.viewport().geometry()
    assert button.geometry().right() == view.right() - MARGIN_PX
    assert button.geometry().bottom() == view.bottom() - MARGIN_PX
    button.click()
    qapp.processEvents()
    assert is_at_bottom(browser)
    assert button.isHidden()
    browser.close()
    browser.deleteLater()
