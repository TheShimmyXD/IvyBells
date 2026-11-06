"""El logo: sello ocre afuera, campana en tinta al centro y fondo transparente."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from ui.blocks.logo import OUTER_RADIUS, app_icon, paint_logo

INK, SEAL = QColor("#1F5266"), QColor("#A8802F")


def _render(size: int = 128) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    paint_logo(painter, QRectF(0, 0, size, size), INK, SEAL)
    painter.end()
    return image


def test_seal_ring_is_ochre_bell_is_ink_and_corners_are_empty(qapp):
    image = _render()
    scale = 128 / 64
    ring = image.pixelColor(int(32 * scale), int((32 - OUTER_RADIUS) * scale))
    bell = image.pixelColor(int(32 * scale), int(30 * scale))
    assert ring.rgb() == SEAL.rgb()
    assert bell.rgb() == INK.rgb()
    assert image.pixelColor(1, 1).alpha() == 0


def test_app_icon_has_every_size(qapp):
    sizes = {size.width() for size in app_icon().availableSizes()}
    assert {16, 32, 256} <= sizes
