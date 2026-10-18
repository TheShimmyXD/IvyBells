"""
Página Transcripción: "Ellos" y "Tú" en dos columnas.

El icono de cada columna abre o cierra su canal, también con la escucha en marcha.

Arriba el estado, el modelo y Iniciar/Detener; abajo las fuentes, la latencia y Guardar .md.
Solo habla con `LiveCoordinator`.

Cada combo de fuente empieza con "Predeterminada", que sigue a la del sistema aunque se
conecten o desconecten equipos; elegir un equipo concreto lo recuerda. Si el elegido no está
conectado se usa la predeterminada sin olvidarlo, y vuelve solo cuando reaparece. La lista
se refresca cada pocos segundos mientras no se escucha, y justo antes de Iniciar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
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
from core.live_view import SOURCES, format_latency, resolve_device, short_device_name
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
# Cada cuánto se vuelve a mirar qué fuentes hay (equipos conectados o desconectados).
SOURCES_REFRESH_MS = 3_000
# Dato del primer elemento del combo: seguir la fuente predeterminada del sistema.
FOLLOW_DEFAULT = ""
# (fuente, título, icono de la columna, icono con el canal cerrado)
VOICES = (
    ("ellos", "Ellos", "speaker-high", "speaker-slash"),
    ("tu", "Tú", "microphone", "microphone-slash"),
)


class LivePage(QWidget):
    """
    Signals
    -------
    devices_chosen(dict) -> la elección del autor por voz (nombre o "" = predeterminada).
    """

    devices_chosen = Signal(dict)

    def __init__(
        self,
        coordinator: LiveCoordinator,
        preferred: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.coordinator = coordinator
        self._preferred = {
            source: (preferred or {}).get(source, FOLLOW_DEFAULT) for source in SOURCES
        }
        self._lists: dict[str, list[str]] = {source: [] for source in SOURCES}
        self._defaults: dict[str, str | None] = dict.fromkeys(SOURCES)
        self._seen: tuple | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(self._build_header())
        columns = QHBoxLayout()
        columns.setSpacing(10)
        self.columns: dict[str, TranscriptColumn] = {}
        for source, title, glyph, closed_glyph in VOICES:
            column = self.columns[source] = TranscriptColumn(title, glyph, closed_glyph)
            column.channel_clicked.connect(lambda s=source: self._on_channel_clicked(s))
            columns.addWidget(column, 1)
        layout.addLayout(columns, 1)
        layout.addLayout(self._build_footer())
        self.refresh_sources()
        self._timer = QTimer(self)
        self._timer.setInterval(SOURCES_REFRESH_MS)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start()
        coordinator.state_changed.connect(self._on_state)
        coordinator.transcript_changed.connect(self.refresh_transcript)
        coordinator.latency_changed.connect(self._on_latency)
        coordinator.sources_changed.connect(self.refresh_channels)
        self._on_state({})
        self.refresh_channels()

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
        for source, title, glyph, _closed_glyph in VOICES:
            row.addWidget(GlyphLabel(glyph, FOOTER_ICON_SIZE, Tone.MUTED))
            box = QComboBox()
            box.setAccessibleName(f"Fuente de {title}")
            box.setMinimumContentsLength(14)
            box.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            box.activated.connect(lambda index, s=source: self._on_device_chosen(s, index))
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

    # -- Fuentes ----------------------------------------------

    def refresh_sources(self) -> None:
        """Vuelve a leer las fuentes; solo rehace los combos si algo cambió."""
        choices = self.coordinator.read_sources()
        self._lists = {
            "ellos": [item.name for item in choices.monitors],
            "tu": [item.name for item in choices.inputs],
        }
        selected = {"ellos": choices.selected.monitor, "tu": choices.selected.microphone}
        self._defaults = {source: item.name if item else None for source, item in selected.items()}
        seen = (tuple(map(tuple, self._lists.values())), tuple(self._defaults.values()))
        if seen == self._seen:
            return
        self._seen = seen
        for source, box in self.source_boxes.items():
            self._fill_box(source, box)

    def _fill_box(self, source: str, box: QComboBox) -> None:
        names, default = self._lists[source], self._defaults[source]
        preferred = self._preferred[source]
        box.blockSignals(True)
        box.clear()
        if names:
            label = short_device_name(default) if default else "sin fuente"
            box.addItem(f"Predeterminada ({label})", FOLLOW_DEFAULT)
            box.setItemData(0, "Sigue a la del sistema", Qt.ItemDataRole.ToolTipRole)
            for name in names:
                box.addItem(short_device_name(name), name)
                box.setItemData(box.count() - 1, name, Qt.ItemDataRole.ToolTipRole)
            index = box.findData(preferred) if preferred in names else 0
            box.setCurrentIndex(max(index, 0))
        else:
            box.addItem("sin fuente", None)
        if preferred and preferred not in names:
            box.setToolTip(
                f"{short_device_name(preferred)} no está conectada: se usa la predeterminada"
            )
        else:
            box.setToolTip("")
        box.blockSignals(False)

    def _on_device_chosen(self, source: str, index: int) -> None:
        """Solo cuando el autor elige en el combo (no al rehacerlo)."""
        choice = self.source_boxes[source].itemData(index)
        if choice is None or choice == self._preferred[source]:
            return
        self._preferred[source] = choice
        self.source_boxes[source].setToolTip("")
        self.devices_chosen.emit({s: name for s, name in self._preferred.items() if name})

    def _on_timer(self) -> None:
        if not self.coordinator.logic.is_busy:
            self.refresh_sources()

    # -- Pedidos al coordinador --------------------------------

    def selected_devices(self) -> dict[str, str]:
        """Las fuentes que se capturarían ahora, por nombre."""
        devices = {}
        for source in SOURCES:
            name = resolve_device(
                self._lists[source], self._preferred[source], self._defaults[source]
            )
            if name:
                devices[source] = name
        return devices

    def toggle_run(self) -> None:
        """Iniciar o Detener; también lo usa el botón del módulo Agente."""
        if self.coordinator.logic.can_stop:
            self.coordinator.stop()
        else:
            self.refresh_sources()
            self.coordinator.start(self.model_selector.current, self.selected_devices())

    def _on_channel_clicked(self, source: str) -> None:
        coordinator = self.coordinator
        if not coordinator.set_source_open(source, not coordinator.is_open(source)):
            self.status.set_status("Queda al menos un canal abierto", Tone.WARNING)

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

    def refresh_channels(self) -> None:
        for source, column in self.columns.items():
            column.set_open(self.coordinator.is_open(source))
            self.refresh_transcript(source)

    def refresh_theme(self) -> None:
        for source in SOURCES:
            self.refresh_transcript(source)

    def _on_latency(self, last: float, median: float) -> None:
        self.latency_label.setText(format_latency(last, median))
