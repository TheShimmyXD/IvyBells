"""
Página Agente (maqueta A): el cliente a la izquierda y lo que responde Claude a la derecha.

Clic izquierdo marca el inicio, clic derecho el final y envía; Esc o Cancelar cancela.
El modelo, el esfuerzo y la cuenta se muestran aquí y se cambian en Configuración.
Solo habla con `AgentCoordinator` (y, por él, con la escucha en vivo).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from coordinator_agent import AgentCoordinator
from core.agent_state import AgentState
from core.claude_model import ClaudeModelConfig
from ui.agent_view import SelectableTranscript, keep_scroll, transcript_html, turns_html
from ui.blocks.icons import GlyphLabel
from ui.blocks.panel import titled_panel
from ui.blocks.segmented import Segment, SegmentedButtons
from ui.blocks.status_line import StatusLine
from ui.theme import ButtonRole, Tone, mono_font, set_role, set_tone, tokens

FOOTER_ICON_SIZE = 15
STATE_TONES = {
    AgentState.IDLE: Tone.INFO,
    AgentState.START_MARKED: Tone.WARNING,
    AgentState.SENDING: Tone.WARNING,
    AgentState.ANSWERED: Tone.OK,
    AgentState.ERROR: Tone.ERROR,
}
SPEAKERS = (
    Segment("ellos", "Ellos", "Lo que suena por la salida"),
    Segment("tu", "Tú", "El micrófono"),
)
HINT = "Clic izquierdo: inicio   Clic derecho: final y enviar   Esc: cancelar"


def config_text(config: ClaudeModelConfig) -> str:
    effort = config.effort or "por defecto"
    account = config.account or "sesión de siempre"
    return f"Claude: {config.model}, esfuerzo {effort}, {account}"


def first_text(seconds: float | None) -> str:
    return (
        "Primer texto -" if seconds is None else f"Primer texto {seconds:.1f} s".replace(".", ",")
    )


class AgentPage(QWidget):
    def __init__(
        self,
        agent: AgentCoordinator,
        toggle_run: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.agent = agent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(self._build_header(toggle_run))
        columns = QHBoxLayout()
        columns.setSpacing(10)
        columns.addWidget(self._build_client(), 1)
        columns.addWidget(self._build_turns(), 1)
        layout.addLayout(columns, 1)
        layout.addLayout(self._build_footer())
        QShortcut(QKeySequence("Esc"), self, activated=agent.cancel)

        agent.state_changed.connect(self._on_state)
        agent.turns_changed.connect(self.refresh_turns)
        agent.marks_changed.connect(self.refresh_transcript)
        agent.settings.config_changed.connect(self._on_config)
        agent.live.transcript_changed.connect(self._on_live_transcript)
        agent.live.state_changed.connect(self._on_live_state)
        self._on_config(agent.settings.config)
        self._on_state({})
        self._on_live_state({})
        self.refresh_theme()

    # -- Construcción ------------------------------------------

    def _build_header(self, toggle_run: Callable[[], None]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.status = StatusLine()
        row.addWidget(self.status, 1)
        self.config_label = QLabel()
        set_tone(self.config_label, Tone.MUTED)
        row.addWidget(self.config_label)
        self.cancel_button = QPushButton("Cancelar")
        set_role(self.cancel_button, ButtonRole.SECONDARY)
        self.cancel_button.clicked.connect(self.agent.cancel)
        row.addWidget(self.cancel_button)
        self.run_button = QPushButton()
        self.run_button.clicked.connect(toggle_run)
        row.addWidget(self.run_button)
        return row

    def _build_client(self) -> QFrame:
        self.speaker_selector = SegmentedButtons(SPEAKERS)
        self.speaker_selector.select(self.agent.speaker)
        self.speaker_selector.changed.connect(self._on_speaker)
        frame, layout = titled_panel("speaker-high", "Cliente", self.speaker_selector)
        self.transcript = SelectableTranscript()
        self.transcript.setAccessibleName("Texto del cliente")
        self.transcript.clicked.connect(self._on_clicked)
        layout.addWidget(self.transcript, 1)
        return frame

    def _build_turns(self) -> QFrame:
        frame, layout = titled_panel("robot", "Agente")
        self.turns_view = QTextBrowser()
        self.turns_view.setFrameShape(QFrame.Shape.NoFrame)
        self.turns_view.setAccessibleName("Respuestas del agente")
        layout.addWidget(self.turns_view, 1)
        return frame

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        hint = QLabel(HINT)
        set_tone(hint, Tone.MUTED)
        row.addWidget(hint)
        row.addStretch(1)
        row.addWidget(GlyphLabel("timer", FOOTER_ICON_SIZE, Tone.MUTED))
        self.first_text_label = QLabel(first_text(None))
        self.first_text_label.setFont(mono_font())
        set_tone(self.first_text_label, Tone.MUTED)
        row.addWidget(self.first_text_label)
        return row

    # -- Eventos -----------------------------------------------

    def _on_clicked(self, phrase: int, offset: int, is_end: bool) -> None:
        if is_end:
            self.agent.mark_end(phrase, offset)
        else:
            self.agent.mark_start(phrase, offset)

    def _on_speaker(self, source: str) -> None:
        self.agent.set_speaker(source)
        self.refresh_transcript()

    def _on_live_transcript(self, source: str) -> None:
        if source == self.agent.speaker:
            self.refresh_transcript()

    # -- Señales -----------------------------------------------

    def _on_state(self, payload: dict) -> None:
        logic = self.agent.logic
        self.status.set_status(logic.status, STATE_TONES[logic.state])
        self.cancel_button.setEnabled(logic.state in (AgentState.START_MARKED, AgentState.SENDING))
        self.speaker_selector.setEnabled(logic.state is not AgentState.SENDING)

    def _on_live_state(self, payload: dict) -> None:
        live = self.agent.live.logic
        self.run_button.setText("Detener" if live.can_stop else "Iniciar")
        set_role(self.run_button, ButtonRole.DANGER if live.can_stop else ButtonRole.PRIMARY)
        self.run_button.setEnabled(live.can_stop or live.can_start)

    def _on_config(self, config: ClaudeModelConfig) -> None:
        self.config_label.setText(config_text(config))

    def refresh_transcript(self) -> None:
        source = self.agent.speaker
        transcript = self.agent.live.transcript
        finals = transcript.finals(source)
        html = transcript_html(
            finals,
            transcript.partial(source),
            self.agent.sent_ranges(source),
            self.agent.start_mark,
            tokens(),
            mono_font().family(),
        )
        self.transcript.show_phrases(html, len(finals))

    def refresh_turns(self) -> None:
        keep_scroll(self.turns_view, turns_html(self.agent.turns, tokens(), mono_font().family()))
        self.first_text_label.setText(first_text(self.agent.last_first_text_s))

    def refresh_theme(self) -> None:
        self.refresh_transcript()
        self.refresh_turns()
