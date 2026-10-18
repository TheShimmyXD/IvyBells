"""
Página Transcripción: "Ellos" y "Tú" en dos columnas.

Arriba el estado, el modelo y Iniciar/Detener; abajo las fuentes, la latencia y Guardar .md.
Solo habla con `LiveCoordinator`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from coordinator_live import DEFAULT_MODEL, MODELS, LiveCoordinator
from core.live_state import LiveState
from core.live_view import SOURCES, format_latency, short_device_name
from ui.blocks.icons import GlyphLabel
from ui.blocks.segmented import Segment, SegmentedButtons
from ui.blocks.status_line import StatusLine
from ui.live_column import TranscriptColumn
from ui.theme import ButtonRole, Tone, mono_font, set_role, set_tone

FOOTER_ICON_SIZE = 15
STATE_TONES = {
    LiveState.STOPPED: Tone.INFO,
    LiveState.LOADING: Tone.WARNING,
    LiveState.LISTENING: Tone.OK,
    LiveState.STOPPING: Tone.WARNING,
    LiveState.ERROR: Tone.ERROR,
}
# (fuente, título, icono de la columna)
VOICES = (("ellos", "Ellos", "speaker-high"), ("tu", "Tú", "microphone"))


class LivePage(QWidget):
    def __init__(self, coordinator: LiveCoordinator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.coordinator = coordinator
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(self._build_header())
        columns = QHBoxLayout()
        columns.setSpacing(10)
        self.columns: dict[str, TranscriptColumn] = {}
        for source, title, glyph in VOICES:
            self.columns[source] = TranscriptColumn(title, glyph)
            columns.addWidget(self.columns[source], 1)
        layout.addLayout(columns, 1)
        layout.addLayout(self._build_footer())
        self._fill_sources()
        coordinator.state_changed.connect(self._on_state)
        coordinator.transcript_changed.connect(self.refresh_transcript)
        coordinator.latency_changed.connect(self._on_latency)
        self._on_state({})

    # -- Construcción ------------------------------------------

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.status = StatusLine()
        row.addWidget(self.status, 1)
        model_label = QLabel("Modelo")
        set_tone(model_label, Tone.MUTED)
        row.addWidget(model_label)
        self.model_selector = SegmentedButtons([Segment(*model) for model in MODELS])
        self.model_selector.select(DEFAULT_MODEL)
        row.addWidget(self.model_selector)
        self.run_button = QPushButton()
        self.run_button.clicked.connect(self.toggle_run)
        row.addWidget(self.run_button)
        return row

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        self.source_boxes: dict[str, QComboBox] = {}
        for source, title, glyph in VOICES:
            row.addWidget(GlyphLabel(glyph, FOOTER_ICON_SIZE, Tone.MUTED))
            box = QComboBox()
            box.setAccessibleName(f"Fuente de {title}")
            box.setMinimumContentsLength(14)
            box.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            self.source_boxes[source] = box
            row.addWidget(box)
            row.addSpacing(8)
        row.addStretch(1)
        row.addWidget(GlyphLabel("timer", FOOTER_ICON_SIZE, Tone.MUTED))
        self.latency_label = QLabel(format_latency(None, None))
        self.latency_label.setFont(mono_font())
        set_tone(self.latency_label, Tone.MUTED)
        row.addWidget(self.latency_label)
        self.save_button = QPushButton("Guardar .md")
        set_role(self.save_button, ButtonRole.SECONDARY)
        self.save_button.clicked.connect(self._on_save_clicked)
        row.addWidget(self.save_button)
        return row

    def _fill_sources(self) -> None:
        choices = self.coordinator.read_sources()
        lists = {"ellos": choices.monitors, "tu": choices.inputs}
        chosen = {"ellos": choices.selected.monitor, "tu": choices.selected.microphone}
        for source, box in self.source_boxes.items():
            box.clear()
            for item in lists[source]:
                box.addItem(short_device_name(item.name), item.name)
                box.setItemData(box.count() - 1, item.name, Qt.ItemDataRole.ToolTipRole)
            if chosen[source] is not None:
                box.setCurrentIndex(box.findData(chosen[source].name))
            if box.count() == 0:
                box.addItem("sin fuente", None)

    # -- Pedidos al coordinador --------------------------------

    def selected_devices(self) -> dict[str, str]:
        devices = {}
        for source, box in self.source_boxes.items():
            if box.currentData():
                devices[source] = box.currentData()
        return devices

    def toggle_run(self) -> None:
        """Iniciar o Detener; también lo usa el botón del módulo Agente."""
        if self.coordinator.logic.can_stop:
            self.coordinator.stop()
        else:
            self.coordinator.start(self.model_selector.current, self.selected_devices())

    def _on_save_clicked(self) -> None:
        last = self.coordinator.last_path
        suggested = str(Path.home() / last.name) if last else ""
        target, _ = QFileDialog.getSaveFileName(
            self, "Guardar transcripción", suggested, "Markdown (*.md)"
        )
        if target and not self.coordinator.save_copy(Path(target)):
            self.status.set_status("No se pudo guardar la transcripción", Tone.ERROR)

    # -- Señales del coordinador -------------------------------

    def _on_state(self, payload: dict) -> None:
        logic = self.coordinator.logic
        self.status.set_status(logic.status, STATE_TONES[logic.state])
        listening = logic.can_stop
        self.run_button.setText("Detener" if listening else "Iniciar")
        set_role(self.run_button, ButtonRole.DANGER if listening else ButtonRole.PRIMARY)
        self.run_button.setEnabled(logic.can_stop or logic.can_start)
        self.model_selector.setEnabled(not logic.is_busy)
        for box in self.source_boxes.values():
            box.setEnabled(not logic.is_busy)
        self.save_button.setEnabled(self.coordinator.last_path is not None or listening)

    def refresh_transcript(self, source: str) -> None:
        transcript = self.coordinator.transcript
        self.columns[source].show_lines(transcript.finals(source), transcript.partial(source))

    def refresh_theme(self) -> None:
        for source in SOURCES:
            self.refresh_transcript(source)

    def _on_latency(self, last: float, median: float) -> None:
        self.latency_label.setText(format_latency(last, median))
