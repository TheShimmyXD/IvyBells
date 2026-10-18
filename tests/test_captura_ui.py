from __future__ import annotations

from PySide6.QtGui import QImage

from captura_ui import CONFIG_STATES, STATES, THEMES, capture_config, capture_states


def test_captures_every_state_and_theme(qapp, tmp_path):
    paths = capture_states(tmp_path)
    assert len(paths) == len(STATES) * len(THEMES)
    for path in paths:
        image = QImage(str(path))
        assert not image.isNull()
        assert image.width() >= 680 and image.height() >= 420


def test_captures_config_page(qapp, tmp_path):
    paths = capture_config(tmp_path)
    assert len(paths) == len(CONFIG_STATES) * len(THEMES)
    assert all(not QImage(str(path)).isNull() for path in paths)
