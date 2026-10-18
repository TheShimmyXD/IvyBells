"""Ficha con borde: icono y título arriba, una línea y debajo el contenido."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.blocks.icons import GlyphLabel
from ui.theme import Kind, Tone, set_kind

TITLE_ICON_SIZE = 16


def titled_panel(
    glyph: str, title: str, extra: QWidget | None = None
) -> tuple[QFrame, QVBoxLayout]:
    """El panel y su layout, ya con el título; `extra` va a la derecha del título."""
    frame = QFrame()
    set_kind(frame, Kind.PANEL)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.setSpacing(8)
    head = QHBoxLayout()
    head.addWidget(GlyphLabel(glyph, TITLE_ICON_SIZE, Tone.INFO))
    label = QLabel(title)
    set_kind(label, Kind.TITLE)
    head.addWidget(label)
    head.addStretch(1)
    if extra is not None:
        head.addWidget(extra)
    layout.addLayout(head)
    rule = QFrame()
    set_kind(rule, Kind.RULE)
    layout.addWidget(rule)
    return frame, layout
