"""Una columna de la ventana: el título de la voz y su texto, el provisional en gris y cursiva."""

from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget

from core.live_view import Line
from ui.blocks.icons import GlyphLabel
from ui.theme import ColorTokens, Kind, Tone, mono_font, set_kind, tokens

TITLE_ICON_SIZE = 16


def column_html(finals: list[Line], partial: Line | None, colors: ColorTokens, mono: str) -> str:
    """Cada frase con su hora en mono encima; el provisional al final con puntos suspensivos."""
    items = [(line, False) for line in finals]
    if partial is not None:
        items.append((partial, True))
    rows = []
    for line, is_partial in items:
        body = escape(line.text)
        if is_partial:
            body = f"<i style='color:{colors.text_muted}'>{body} ...</i>"
        rows.append(
            f"<p style='margin-bottom:8px'><span style='color:{colors.text_muted}; "
            f"font-family:{mono}; font-size:small'>{line.clock}</span><br>{body}</p>"
        )
    return f"<div style='color:{colors.text}'>{''.join(rows)}</div>"


class TranscriptColumn(QFrame):
    """Panel con el título de una voz y el texto que se va escribiendo."""

    def __init__(self, title: str, glyph: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_kind(self, Kind.PANEL)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(GlyphLabel(glyph, TITLE_ICON_SIZE, Tone.INFO))
        label = QLabel(title)
        set_kind(label, Kind.TITLE)
        head.addWidget(label)
        head.addStretch(1)
        layout.addLayout(head)
        rule = QFrame()
        set_kind(rule, Kind.RULE)
        layout.addWidget(rule)
        self.browser = QTextBrowser()
        self.browser.setFrameShape(QFrame.Shape.NoFrame)
        self.browser.setAccessibleName(title)
        layout.addWidget(self.browser, 1)

    def show_lines(self, finals: list[Line], partial: Line | None) -> None:
        """Repinta el texto y baja al final solo si el lector ya estaba abajo."""
        bar = self.browser.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        previous = bar.value()
        self.browser.setHtml(column_html(finals, partial, tokens(), mono_font().family()))
        bar.setValue(bar.maximum() if at_bottom else previous)
