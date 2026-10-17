# Copiado de vid2aud v1.1.1 (commit d03adf5); los cambios propios de IvyBells se anotan.
"""Linea de estado: icono del color del tono y una frase corta.

El color lo lleva el icono; el texto va en gris salvo en un error, que tiene
que leerse. Sin texto la linea se oculta.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ui.blocks.icons import GlyphLabel
from ui.theme import Tone, set_tone

ICON_SIZE = 16
TONE_ICONS = {
    Tone.OK: "check-circle",
    Tone.WARNING: "warning-circle",
    Tone.ERROR: "x-circle",
    Tone.INFO: "info",
}


class StatusLine(QWidget):
    """``set_status(texto, tono)``; el tono elige el icono y su color."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tone: Tone | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.icon_label = GlyphLabel("info", ICON_SIZE, Tone.INFO)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        row.addWidget(self.icon_label)
        row.addWidget(self.text_label, 1)
        self.set_status("")

    def set_status(self, text: str, tone: Tone | None = None) -> None:
        self._tone = tone
        self.text_label.setText(text)
        icon = TONE_ICONS.get(tone) if tone else None
        if icon:
            self.icon_label.set_glyph(icon, tone)
        self.icon_label.setVisible(icon is not None)
        set_tone(self.text_label, Tone.ERROR if tone is Tone.ERROR else Tone.MUTED)
        self.setVisible(bool(text))

    def text(self) -> str:
        return self.text_label.text()

    def tone(self) -> Tone | None:
        return self._tone
