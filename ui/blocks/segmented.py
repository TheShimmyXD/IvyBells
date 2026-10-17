# Copiado de vid2aud v1.1.1 (commit d03adf5); los cambios propios de IvyBells se anotan.
"""Botones unidos en una sola pieza, uno elegido a la vez.

Solo los extremos van redondeados; el elegido, relleno con la tinta. La
explicacion de cada opcion va en su ayuda (tooltip).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from ui.theme import Kind, set_kind


class Segment(NamedTuple):
    key: str
    name: str
    tip: str = ""


class SegmentedButtons(QWidget):
    """
    Signals
    -------
    changed(str) -> la clave del segmento elegido.
    """

    changed = Signal(str)

    def __init__(self, segments: Sequence[Segment], parent=None) -> None:
        super().__init__(parent)
        self._segments = tuple(segments)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for index, segment in enumerate(self._segments):
            button = QPushButton(segment.name)
            button.setCheckable(True)
            if segment.tip:
                button.setToolTip(segment.tip)
            button.setAccessibleName(segment.name)
            if index == 0:
                button.setObjectName("first")
            if index == len(self._segments) - 1:
                button.setObjectName("last")
            # Despues del nombre: las esquinas de los extremos dependen de el.
            set_kind(button, Kind.SEGMENT)
            self._group.addButton(button, index)
            layout.addWidget(button)
            self.buttons[segment.key] = button
        layout.addStretch(1)
        self.buttons[self._segments[0].key].setChecked(True)
        self._group.idToggled.connect(self._on_toggled)

    @property
    def current(self) -> str:
        return self._segments[max(self._group.checkedId(), 0)].key

    def select(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def _on_toggled(self, index: int, checked: bool) -> None:
        # Al cambiar llegan dos avisos (el que se apaga y el que se prende): solo cuenta este.
        if checked:
            self.changed.emit(self._segments[index].key)
