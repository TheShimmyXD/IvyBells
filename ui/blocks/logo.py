"""El logo de IvyBells: una campana maciza dentro del sello de la familia.

Se dibuja con QPainter sobre una rejilla de 64, en cualquier tamano y con los
colores del tema; no hay archivo de imagen. El sello (anillo ocre y anillo
punteado) es el mismo de vid2aud y Molink; el glifo es una campana en tinta con
el badajo en ocre.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTransform

from ui.theme import seal_colors

GRID = 64.0
CENTER = QPointF(32, 32)
OUTER_RADIUS, OUTER_WIDTH = 29.0, 3.0
INNER_RADIUS, INNER_WIDTH = 23.5, 2.0
# Trazo de 2.2 y hueco de 3.4 en la rejilla; Qt los mide en anchos de linea.
INNER_DASHES = (2.2 / INNER_WIDTH, 3.4 / INNER_WIDTH)
# La campana se dibuja en su propia rejilla de 64 y se reduce al centro del sello.
BELL_SCALE = 0.70
BELL_CENTER_Y = 31.0
# Borde redondeado de la campana, medido en la rejilla del sello.
BELL_EDGE_WIDTH = 2.4
CLAPPER_CENTER, CLAPPER_RADIUS = QPointF(32, 51.5), 4.6
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
PIXEL_RATIO = 2.0


def _bell_transform() -> QTransform:
    """Lleva la rejilla de la campana al centro del sello."""
    transform = QTransform()
    transform.translate(32, BELL_CENTER_Y)
    transform.scale(BELL_SCALE, BELL_SCALE)
    transform.translate(-32, -32)
    return transform


def _bell_body() -> QPainterPath:
    """Cuerpo y asa de la campana, ya en la rejilla del sello."""
    body = QPainterPath()
    body.moveTo(15, 45)
    body.cubicTo(19, 41, 18, 33, 19, 27)
    body.cubicTo(20, 18, 26, 14, 32, 14)
    body.cubicTo(38, 14, 44, 18, 45, 27)
    body.cubicTo(46, 33, 45, 41, 49, 45)
    body.closeSubpath()
    return _bell_transform().map(body)


def _round_pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _paint_seal(painter: QPainter, seal: QColor) -> None:
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(seal, OUTER_WIDTH))
    painter.drawEllipse(CENTER, OUTER_RADIUS, OUTER_RADIUS)
    dashed = QPen(seal, INNER_WIDTH)
    dashed.setDashPattern(list(INNER_DASHES))
    painter.setPen(dashed)
    painter.drawEllipse(CENTER, INNER_RADIUS, INNER_RADIUS)


def _paint_bell(painter: QPainter, ink: QColor, seal: QColor) -> None:
    transform = _bell_transform()
    painter.setPen(_round_pen(ink, BELL_EDGE_WIDTH))
    painter.setBrush(ink)
    painter.drawPath(_bell_body())
    painter.drawLine(transform.map(QPointF(32, 14)), transform.map(QPointF(32, 9.5)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(seal)
    radius = CLAPPER_RADIUS * BELL_SCALE
    painter.drawEllipse(transform.map(CLAPPER_CENTER), radius, radius)


def paint_logo(painter: QPainter, rect: QRectF, ink: QColor, seal: QColor) -> None:
    """Dibuja el sello con la campana dentro de ``rect`` (cuadrado)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(rect.topLeft())
    scale = min(rect.width(), rect.height()) / GRID
    painter.scale(scale, scale)
    _paint_seal(painter, seal)
    _paint_bell(painter, ink, seal)
    painter.restore()


def logo_pixmap(size: int, on_dark: bool = False, pixel_ratio: float = PIXEL_RATIO) -> QPixmap:
    """El logo de ``size`` px; ``on_dark`` para la barra lateral oscura."""
    pixmap = QPixmap(int(size * pixel_ratio), int(size * pixel_ratio))
    pixmap.setDevicePixelRatio(pixel_ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    paint_logo(painter, QRectF(0, 0, size, size), *seal_colors(on_dark))
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    """Icono de la ventana en todos los tamanos, a resolucion 1."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(logo_pixmap(size, pixel_ratio=1.0))
    return icon
