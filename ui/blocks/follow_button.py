"""
Botón flotante "Seguir en vivo" sobre un texto que se desplaza (QTextBrowser).

Aparece en la esquina inferior derecha del texto cuando el lector se aleja del final y
desaparece al volver; un clic baja al final, y desde ahí el texto nuevo se sigue solo.
Es translúcido para no tapar la lectura y se vuelve sólido con el mouse encima: el fondo
con `:hover` en el QSS y el icono aquí. Sin QGraphicsOpacityEffect: con varios botones,
PySide se caía al destruirlos al salir (violación de segmento tras pasar las pruebas).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QAbstractScrollArea, QToolButton

from ui.blocks.icons import REPAINT_EVENTS, glyph_pixmap
from ui.theme import ButtonRole, set_role, tokens
from ui.theme_qss import FLOATING_IDLE_ALPHA

FOLLOW_GLYPH = "arrow-down"
BUTTON_SIZE = 34
ICON_SIZE = 16
# Separación del borde inferior y del derecho del texto (la barra queda a la derecha).
MARGIN_PX = 10
# Píxeles de holgura para contar al lector como "abajo".
BOTTOM_SLACK_PX = 4
TIP = "Seguir en vivo: bajar al final y seguir el texto nuevo"


def is_at_bottom(area: QAbstractScrollArea) -> bool:
    """True si el texto está al final (o cabe entero)."""
    bar = area.verticalScrollBar()
    return bar.value() >= bar.maximum() - BOTTOM_SLACK_PX


class FollowButton(QToolButton):
    """Botón redondo que flota sobre `area` y la baja al final."""

    def __init__(self, area: QAbstractScrollArea) -> None:
        super().__init__(area)
        self._area = area
        self._pending = False
        self.solid = False  # antes de set_role: el cambio de estilo repinta el icono
        set_role(self, ButtonRole.FLOATING)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(TIP)
        self.setAccessibleName(TIP)
        self.clicked.connect(self.follow)
        bar = area.verticalScrollBar()
        bar.valueChanged.connect(self._schedule)
        bar.rangeChanged.connect(self._schedule)
        self._repaint_icon()
        self.hide()

    def follow(self) -> None:
        """Baja al final del texto y se oculta."""
        bar = self._area.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.refresh()

    def refresh(self) -> None:
        """Se muestra (en su esquina) solo si el texto no está al final."""
        self._pending = False
        away = not is_at_bottom(self._area)
        if away:
            self._place()
            self.raise_()
        self.setVisible(away)

    def _schedule(self, *_args: int) -> None:
        # Al repintar, la barra pasa por estados a medias: se mira una vez, ya quieta.
        # Al redimensionar cambia el rango y aquí se reubica (sin eventFilter en Python:
        # Qt lo llamaba al destruir los widgets y el proceso podía caerse al salir).
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self, self.refresh)

    def _place(self) -> None:
        view = self._area.viewport().geometry()
        self.move(
            view.right() + 1 - BUTTON_SIZE - MARGIN_PX,
            view.bottom() + 1 - BUTTON_SIZE - MARGIN_PX,
        )

    def set_solid(self, solid: bool) -> None:
        """Icono sólido (mouse encima) o translúcido."""
        self.solid = solid
        self._repaint_icon()

    def enterEvent(self, event: QEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self.set_solid(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self.set_solid(False)
        super().leaveEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        super().changeEvent(event)
        if event.type() in REPAINT_EVENTS:
            self._repaint_icon()

    def _repaint_icon(self) -> None:
        color = QColor(tokens().on_brand)
        if not self.solid:
            # La flecha, algo más firme que el fondo para que se lea sobre el texto.
            color.setAlphaF(FLOATING_IDLE_ALPHA + (1 - FLOATING_IDLE_ALPHA) / 2)
        self.setIcon(QIcon(glyph_pixmap(FOLLOW_GLYPH, color, ICON_SIZE)))
