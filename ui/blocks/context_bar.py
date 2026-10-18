"""
Barra de contexto: cuánto de la ventana del modelo ocupa el próximo envío, por partes.

Cada parte tiene su color: reglas y perfil, contexto, historial y fragmento. La cifra
lleva "~" porque es una estimación; la real del último envío (con su primer texto y su
caché) va al lado o en la ayuda. Compacta para el pie del Agente; con leyenda para
Configuración. Solo recibe un `ContextBudget`.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from core.context_budget import BudgetPart, ContextBudget, format_tokens
from ui.theme import Tone, mono_font, set_tone, tokens

# Nombre del token de color de cada parte.
PART_COLORS = {"rules": "brand", "context": "ok", "history": "warning", "fragment": "text_muted"}
LEVEL_TONES = {"ok": Tone.MUTED, "warning": Tone.WARNING, "error": Tone.ERROR}
COMPACT_WIDTH = 96
STRIP_HEIGHT = 8
DETAILED_STRIP_HEIGHT = 12
SWATCH_SIZE = 10
# Una parte que ocupa algo se ve aunque sea mínima frente a la ventana.
MIN_SEGMENT_PX = 2.0
# Sin ventana medida la barra se llena por proporciones: va más tenue.
UNMEASURED_ALPHA = 110


def _thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def part_text(part: BudgetPart) -> str:
    """ "Contexto ~31,3 k"; el historial con su tope de caracteres."""
    text = f"{part.label} ~{format_tokens(part.tokens)}"
    if part.limit_chars:
        text += f" ({_thousands(part.chars)} de {_thousands(part.limit_chars)} car.)"
    return text


def budget_tooltip(budget: ContextBudget) -> str:
    lines = [budget.summary(), *(part_text(part) for part in budget.parts)]
    if budget.last_summary():
        lines.append(budget.last_summary())
    return "\n".join(lines)


class _Strip(QWidget):
    """La tira de colores; se pinta con los tokens del tema aplicado."""

    def __init__(self, height: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self.parts: list[tuple[int, str]] = []
        self.scale = 0
        self.measured = True

    def show_parts(self, parts: list[tuple[int, str]], scale: int, measured: bool) -> None:
        self.parts, self.scale, self.measured = parts, scale, measured
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        colors = tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        outline = QPainterPath()
        outline.addRoundedRect(rect, 3, 3)
        painter.setPen(QColor(colors.border))
        painter.setBrush(QColor(colors.surface_alt))
        painter.drawPath(outline)
        if self.scale <= 0:
            return
        painter.setClipPath(outline)
        painter.setPen(Qt.PenStyle.NoPen)
        x = rect.left()
        for amount, color_name in self.parts:
            if amount <= 0 or x >= rect.right():
                continue
            width = max(MIN_SEGMENT_PX, rect.width() * amount / self.scale)
            color = QColor(getattr(colors, color_name))
            if not self.measured:
                color.setAlpha(UNMEASURED_ALPHA)
            painter.fillRect(
                QRectF(x, rect.top(), min(width, rect.right() - x), rect.height()), color
            )
            x += width


class ContextBar(QWidget):
    """``set_budget(budget)``; ``detailed`` agrega la leyenda y la cifra real en líneas."""

    def __init__(self, detailed: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detailed = detailed
        self.budget: ContextBudget | None = None
        self.summary_label = QLabel()
        self.summary_label.setFont(mono_font())
        self.summary_label.setAccessibleName("Uso del contexto")
        if detailed:
            self._build_detailed()
        else:
            self._build_compact()

    # -- Construcción ------------------------------------------

    def _build_compact(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.strip = _Strip(STRIP_HEIGHT)
        self.strip.setFixedWidth(COMPACT_WIDTH)
        row.addWidget(self.strip)
        row.addWidget(self.summary_label)

    def _build_detailed(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.summary_label)
        self.strip = _Strip(DETAILED_STRIP_HEIGHT)
        self.strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.strip)
        legend = QHBoxLayout()
        legend.setSpacing(6)
        self.swatches: dict[str, QLabel] = {}
        self.part_labels: dict[str, QLabel] = {}
        for key in PART_COLORS:
            swatch = QLabel()
            swatch.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
            label = QLabel()
            set_tone(label, Tone.MUTED)
            legend.addWidget(swatch)
            legend.addWidget(label)
            legend.addSpacing(10)
            self.swatches[key], self.part_labels[key] = swatch, label
        legend.addStretch(1)
        layout.addLayout(legend)
        self.last_label = QLabel()
        self.last_label.setWordWrap(True)
        set_tone(self.last_label, Tone.MUTED)
        layout.addWidget(self.last_label)

    # -- Datos -------------------------------------------------

    def set_budget(self, budget: ContextBudget) -> None:
        self.budget = budget
        self._render()

    def refresh_theme(self) -> None:
        self._render()

    def _render(self) -> None:
        budget = self.budget
        if budget is None:
            return
        measured = budget.window is not None
        self.strip.show_parts(
            [(part.tokens, PART_COLORS[part.key]) for part in budget.parts],
            budget.window or budget.estimated_tokens,
            measured,
        )
        self.summary_label.setText(budget.summary(short=not self.detailed))
        set_tone(self.summary_label, LEVEL_TONES[budget.level])
        self.setToolTip(budget_tooltip(budget))
        if not self.detailed:
            return
        colors = tokens()
        for part in budget.parts:
            color = getattr(colors, PART_COLORS[part.key])
            self.swatches[part.key].setStyleSheet(f"background: {color}; border-radius: 2px;")
            self.part_labels[part.key].setText(part_text(part))
        self.last_label.setText(
            budget.last_summary() or "Sin envíos todavía: la cifra es una estimación."
        )
