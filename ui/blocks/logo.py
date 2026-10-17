"""El logo de IvyBells: una campana con dos voces.

Se dibuja con QPainter sobre una rejilla de 64, en cualquier tamano y con los
colores del tema; no hay archivo de imagen. Las ondas de la izquierda van en
tinta (Ellos) y las de la derecha en ocre (Tú), como las dos columnas.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from ui.theme import seal_colors

GRID = 64.0
BODY_WIDTH = 3.2
CLAPPER_CENTER, CLAPPER_RADIUS = QPointF(32, 50.5), 3.6
# Ondas: (radio, ancho) con centro en (32, 30); cada una abarca 50 grados por lado.
WAVES = ((24.0, 2.6), (29.5, 2.6))
WAVE_CENTER_Y = 30.0
WAVE_SPAN_DEG = 50
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
PIXEL_RATIO = 2.0


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _bell_body() -> QPainterPath:
    body = QPainterPath()
    body.moveTo(15, 45)
    body.cubicTo(19, 41, 18, 33, 19, 27)
    body.cubicTo(20, 18, 26, 14, 32, 14)
    body.cubicTo(38, 14, 44, 18, 45, 27)
    body.cubicTo(46, 33, 45, 41, 49, 45)
    body.closeSubpath()
    return body


def paint_logo(painter: QPainter, rect: QRectF, ink: QColor, seal: QColor) -> None:
    """Dibuja la campana dentro de ``rect`` (cuadrado)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(rect.topLeft())
    scale = min(rect.width(), rect.height()) / GRID
    painter.scale(scale, scale)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(_pen(ink, BODY_WIDTH))
    painter.drawPath(_bell_body())
    painter.drawLine(QPointF(32, 14), QPointF(32, 9.5))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(seal)
    painter.drawEllipse(CLAPPER_CENTER, CLAPPER_RADIUS, CLAPPER_RADIUS)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    half = WAVE_SPAN_DEG // 2
    for radius, width in WAVES:
        arc = QRectF(32 - radius, WAVE_CENTER_Y - radius, 2 * radius, 2 * radius)
        # Qt mide los arcos en dieciseisavos de grado, desde las 3 en contra del reloj.
        painter.setPen(_pen(ink, width))
        painter.drawArc(arc, (180 - half) * 16, WAVE_SPAN_DEG * 16)
        painter.setPen(_pen(seal, width))
        painter.drawArc(arc, -half * 16, WAVE_SPAN_DEG * 16)
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
