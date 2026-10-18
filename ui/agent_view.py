"""
Vistas del módulo Agente: el texto del cliente que se marca con clics y la lista de turnos.

Cada frase final es un párrafo: la hora, un salto de línea y el texto. El salto (`<br>`)
queda en el documento como separador de línea, así que la posición del clic dentro del
texto es lo que viene después de él.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QTextBrowser, QWidget

from coordinator_agent import AgentTurn
from core.agent_selection import WordPos
from core.live_view import Line
from ui.theme import ColorTokens

LINE_SEPARATOR = " "
QUOTE_CHARS = 90


def word_marks(
    phrase: int, words: list[str], ranges: list[tuple[WordPos, WordPos]], start: WordPos | None
) -> list[str]:
    """Por palabra: "start" (frase del inicio marcado), "sent" (ya enviada) o "".

    El Agente envía frases completas, así que el inicio resalta toda su frase.
    """
    marks = []
    for number in range(len(words)):
        pos = WordPos(phrase, number)
        if start is not None and start.phrase == phrase:
            marks.append("start")
        elif any(a <= pos <= b for a, b in ranges):
            marks.append("sent")
        else:
            marks.append("")
    return marks


def _marked_text(words: list[str], marks: list[str], colors: ColorTokens) -> str:
    styles = {
        "sent": f"background:{colors.brand_soft}",
        "start": f"background:{colors.brand}; color:{colors.on_brand}",
    }
    runs: list[tuple[str, list[str]]] = []
    for word, mark in zip(words, marks, strict=True):
        if runs and runs[-1][0] == mark:
            runs[-1][1].append(escape(word))
        else:
            runs.append((mark, [escape(word)]))
    # Tramos seguidos en un solo span, para que el resaltado no se corte en los espacios.
    return " ".join(
        f"<span style='{styles[mark]}'>{' '.join(ws)}</span>" if mark else " ".join(ws)
        for mark, ws in runs
    )


def transcript_html(
    finals: list[Line],
    partial: Line | None,
    ranges: list[tuple[WordPos, WordPos]],
    start: WordPos | None,
    colors: ColorTokens,
    mono: str,
) -> str:
    rows = []
    for phrase, line in enumerate(finals):
        words = line.text.split()
        body = _marked_text(words, word_marks(phrase, words, ranges, start), colors)
        rows.append(
            f"<p style='margin-bottom:8px'><span style='color:{colors.text_muted}; "
            f"font-family:{mono}; font-size:small'>{line.clock}</span><br>{body}</p>"
        )
    if partial is not None:
        rows.append(
            f"<p><span style='color:{colors.text_muted}; font-family:{mono}; "
            f"font-size:small'>{partial.clock}</span><br>"
            f"<i style='color:{colors.text_muted}'>{escape(partial.text)} ...</i></p>"
        )
    return f"<div style='color:{colors.text}'>{''.join(rows)}</div>"


def _quote(turn: AgentTurn) -> str:
    text = " ".join(line.text for line in turn.selection.lines)
    return text if len(text) <= QUOTE_CHARS else text[: QUOTE_CHARS - 3] + "..."


def turns_html(turns: list[AgentTurn], colors: ColorTokens, mono: str) -> str:
    """Cada turno: la hora y la cita corta de lo enviado; debajo la respuesta."""
    out = []
    for turn in turns:
        dots = f" <span style='color:{colors.text_muted}'>...</span>"
        if turn.error:
            body = (
                escape(turn.answer)
                + f"<br><span style='color:{colors.error}'>Error: {escape(turn.error)}</span>"
            )
        elif turn.cancelled:
            body = escape(turn.answer) + f" <i style='color:{colors.text_muted}'>(cancelado)</i>"
        elif not turn.done:
            body = (
                escape(turn.answer) + dots
                if turn.answer
                else (f"<i style='color:{colors.text_muted}'>Esperando a {turn.model}...</i>")
            )
        else:
            body = escape(turn.answer)
        out.append(
            f"<p style='margin-top:10px; margin-bottom:2px; color:{colors.text_muted}; "
            f"font-size:small'><span style='font-family:{mono}'>{turn.clock}</span>"
            f"&nbsp;&nbsp;<i>«{escape(_quote(turn))}»</i></p>"
            f"<p style='margin-top:0; margin-bottom:10px'>{body}</p>"
        )
    return f"<div style='color:{colors.text}'>{''.join(out)}</div>"


def keep_scroll(browser: QTextBrowser, html: str) -> None:
    """Repinta y baja al final solo si el lector ya estaba abajo."""
    bar = browser.verticalScrollBar()
    at_bottom = bar.value() >= bar.maximum() - 4
    previous = bar.value()
    browser.setHtml(html)
    bar.setValue(bar.maximum() if at_bottom else previous)


class SelectableTranscript(QTextBrowser):
    """
    Signals
    -------
    clicked(int, int, bool) -> frase final, posición del clic en su texto y si fue el
                               clic derecho (el final del rango).
    """

    clicked = Signal(int, int, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

    def show_phrases(self, html: str, finals: int) -> None:
        """Pinta el texto y marca cada párrafo con el número de su frase final."""
        keep_scroll(self, html)
        block = self.document().begin()
        phrase = 0
        while block.isValid():
            if block.text().strip() and phrase < finals:
                block.setUserState(phrase)
                phrase += 1
            else:
                block.setUserState(-1)
            block = block.next()

    def phrase_at(self, point) -> tuple[int, int] | None:
        """(frase, posición en su texto) bajo un punto del área visible, o None."""
        cursor = self.cursorForPosition(point)
        block = cursor.block()
        if block.userState() < 0:
            return None
        separator = block.text().find(LINE_SEPARATOR)
        offset = cursor.positionInBlock() - (separator + 1)
        return block.userState(), max(offset, 0)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        button = event.button()
        if button not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            super().mousePressEvent(event)
            return
        self.setFocus()
        hit = self.phrase_at(event.position().toPoint())
        if hit is not None:
            self.clicked.emit(hit[0], hit[1], button == Qt.MouseButton.RightButton)
        event.accept()
