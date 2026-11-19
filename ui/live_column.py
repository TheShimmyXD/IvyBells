"""
Una columna de la ventana: el título de la voz y su texto, el provisional en gris y cursiva.

El icono del título abre o cierra el canal; cerrado, todo se ve en gris.
Si el lector se aleja del final, "Seguir en vivo" flota sobre el texto (`FollowButton`).
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget

from core.live_view import Line
from ui.blocks.follow_button import FollowButton, is_at_bottom
from ui.blocks.icons import GlyphButton
from ui.theme import (
    ButtonRole,
    ColorTokens,
    Kind,
    Tone,
    mono_font,
    set_kind,
    set_role,
    set_tone,
    tokens,
)

TITLE_ICON_SIZE = 16


def _resume_row(clock: str, colors: ColorTokens, mono: str) -> str:
    return (
        f"<p align='center' style='margin-top:6px; margin-bottom:10px; "
        f"color:{colors.text_muted}; font-family:{mono}; font-size:small'>"
        f"&mdash;&mdash; Reanudada {escape(clock)} &mdash;&mdash;</p>"
    )


def column_html(
    finals: list[Line],
    partial: Line | None,
    colors: ColorTokens,
    mono: str,
    muted: bool = False,
    resumes: Sequence[tuple[int, str]] = (),
) -> str:
    """
    Cada frase con su hora en mono encima; el provisional al final con puntos suspensivos.
    `muted` (canal cerrado) pone todo el texto en gris. `resumes` son las reanudaciones
    (antes de qué frase y a qué hora): una línea gris centrada en su sitio.
    """
    items = [(line, False) for line in finals]
    if partial is not None:
        items.append((partial, True))
    marks: dict[int, str] = dict(resumes)
    rows = []
    for index, (line, is_partial) in enumerate(items):
        if index in marks:
            rows.append(_resume_row(marks.pop(index), colors, mono))
        body = escape(line.text)
        if is_partial:
            body = f"<i style='color:{colors.text_muted}'>{body} ...</i>"
        rows.append(
            f"<p style='margin-bottom:8px'><span style='color:{colors.text_muted}; "
            f"font-family:{mono}; font-size:small'>{line.clock}</span><br>{body}</p>"
        )
    # Reanudada sin frases todavía: la marca va al final.
    rows += [_resume_row(clock, colors, mono) for clock in marks.values()]
    color = colors.text_muted if muted else colors.text
    return f"<div style='color:{color}'>{''.join(rows)}</div>"


class TranscriptColumn(QFrame):
    """
    Panel con el título de una voz y el texto que se va escribiendo.

    Signals
    -------
    channel_clicked() -> clic en el icono del título (abrir o cerrar el canal).
    """

    channel_clicked = Signal()

    def __init__(
        self, title: str, glyph: str, closed_glyph: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._glyphs = (glyph, closed_glyph)
        self.is_open = True
        set_kind(self, Kind.PANEL)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        head = QHBoxLayout()
        self.channel_button = GlyphButton(glyph, "", TITLE_ICON_SIZE, tone=Tone.INFO)
        set_role(self.channel_button, ButtonRole.QUIET)
        self.channel_button.clicked.connect(self.channel_clicked)
        head.addWidget(self.channel_button)
        self.title_label = QLabel(title)
        set_kind(self.title_label, Kind.TITLE)
        head.addWidget(self.title_label)
        self.closed_label = QLabel("canal cerrado")
        set_tone(self.closed_label, Tone.MUTED)
        head.addWidget(self.closed_label)
        head.addStretch(1)
        layout.addLayout(head)
        rule = QFrame()
        set_kind(rule, Kind.RULE)
        layout.addWidget(rule)
        self.browser = QTextBrowser()
        self.browser.setFrameShape(QFrame.Shape.NoFrame)
        self.browser.setAccessibleName(title)
        layout.addWidget(self.browser, 1)
        self.follow_button = FollowButton(self.browser)
        self.set_open(True)

    def set_open(self, is_open: bool) -> None:
        """Cerrado: icono tachado, título en gris y el aviso; el texto ya escrito se conserva."""
        self.is_open = is_open
        glyph = self._glyphs[0 if is_open else 1]
        self.channel_button.set_glyph(glyph, Tone.INFO if is_open else Tone.MUTED)
        tip = f"{'Cerrar' if is_open else 'Abrir'} el canal de {self._title}"
        self.channel_button.setToolTip(tip)
        self.channel_button.setAccessibleName(tip)
        set_tone(self.title_label, None if is_open else Tone.MUTED)
        self.closed_label.setVisible(not is_open)

    def show_lines(
        self,
        finals: list[Line],
        partial: Line | None,
        resumes: Sequence[tuple[int, str]] = (),
    ) -> None:
        """Repinta el texto y baja al final solo si el lector ya estaba abajo."""
        bar = self.browser.verticalScrollBar()
        at_bottom = self.at_bottom()
        previous = bar.value()
        self.browser.setHtml(
            column_html(finals, partial, tokens(), mono_font().family(), not self.is_open, resumes)
        )
        bar.setValue(bar.maximum() if at_bottom else previous)

    def at_bottom(self) -> bool:
        """True si el lector está al final del texto (o el texto cabe entero)."""
        return is_at_bottom(self.browser)

    def scroll_to_end(self) -> None:
        """Baja al final; desde ahí `show_lines` vuelve a seguir el texto nuevo."""
        self.follow_button.follow()
