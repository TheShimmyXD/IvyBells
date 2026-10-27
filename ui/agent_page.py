"""
Página Agente (maqueta A): el cliente a la izquierda y lo que responde Claude a la derecha.

Clic izquierdo marca el inicio, clic derecho el final y envía; Esc o Cancelar cancela.
En el modo anticipado se envía solo al terminar cada turno del interlocutor, la
respuesta sale en una tarjeta y la columna derecha es más ancha; los clics siguen.
El modelo, el esfuerzo y la cuenta se muestran aquí y se cambian en Configuración; en el
pie, cuánto de la ventana ocupa el envío y el primer texto y la caché del último.
Con el selector "Agente | Chat", la columna derecha pasa al chat propio del autor
(`ChatPanel`) y el agente sigue trabajando detrás.
Solo habla con `AgentCoordinator` y `ChatCoordinator` (y, por ellos, con la escucha en vivo).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from coordinator_agent import AgentCoordinator
from coordinator_chat import ChatCoordinator
from core.agent_ahead import AHEAD, MANUAL, TURN_SILENCE_S
from core.agent_state import AgentState
from core.claude_model import ClaudeModelConfig
from core.context_budget import format_percent
from ui.agent_view import (
    SelectableTranscript,
    ahead_html,
    keep_scroll,
    transcript_html,
    turns_html,
)
from ui.blocks.context_bar import ContextBar
from ui.blocks.icons import GlyphLabel
from ui.blocks.panel import titled_panel
from ui.blocks.segmented import Segment, SegmentedButtons
from ui.blocks.status_line import StatusLine
from ui.chat_view import ChatPanel
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
MODES = (
    Segment(MANUAL, "Manual", "Envía lo que marcas con clics"),
    Segment(AHEAD, "Anticipado", "Responde solo al terminar cada turno del interlocutor"),
)
HINT = "Clic izquierdo: inicio   Clic derecho: final y enviar   Esc: cancelar"
HINT_AHEAD = f"Responde tras {TURN_SILENCE_S:.1f} s de silencio".replace(".", ",") + (
    "   Clics: envío forzado   Esc: cancelar"
)
FIRST_TEXT_TIPS = {
    MANUAL: "Desde el clic derecho hasta el primer texto de la respuesta",
    AHEAD: "Desde que llegó la última frase del turno hasta el primer texto de la respuesta",
}
PANELS = (
    Segment("agent", "Agente", "Las respuestas del agente"),
    Segment("chat", "Chat", "Tu chat con Claude: sin perfil, con el contexto y los dos canales"),
)
# Columnas (texto, respuestas): en anticipado importan más las respuestas.
STRETCH = {MANUAL: (1, 1), AHEAD: (2, 3)}


def config_text(config: ClaudeModelConfig, profile: str = "") -> str:
    """Corto, para la cabecera; la cuenta va en la ayuda (`config_tip`)."""
    return f"{config.model}, {config.effort or 'por defecto'}, perfil {profile or 'ninguno'}"


def config_tip(config: ClaudeModelConfig) -> str:
    account = config.account or "sesión de siempre"
    return f"Agente: modelo {config.model}, esfuerzo {config.effort or 'por defecto'}, {account}"


def first_text(seconds: float | None, cached: float | None = None) -> str:
    if seconds is None:
        return "Primer texto -"
    text = f"Primer texto {seconds:.1f} s".replace(".", ",")
    return text if cached is None else f"{text}, caché {format_percent(cached)}"


class AgentPage(QWidget):
    """
    Signals
    -------
    panel_changed(str) -> la columna derecha pasó a "agent" o "chat".
    """

    panel_changed = Signal(str)

    def __init__(
        self,
        agent: AgentCoordinator,
        toggle_run: Callable[[], None],
        chat: ChatCoordinator | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.agent = agent
        self.chat = chat
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(self._build_header(toggle_run))
        self.columns = QHBoxLayout()
        self.columns.setSpacing(10)
        self.columns.addWidget(self._build_client(), 1)
        self.right = QStackedWidget()
        self.right.addWidget(self._build_turns())
        self.chat_panel = ChatPanel(chat) if chat is not None else None
        if self.chat_panel is not None:
            self.right.addWidget(self.chat_panel)
        self.columns.addWidget(self.right, 1)
        layout.addLayout(self.columns, 1)
        layout.addLayout(self._build_footer())
        QShortcut(QKeySequence("Esc"), self, activated=agent.cancel)

        agent.state_changed.connect(self._on_state)
        agent.turns_changed.connect(self.refresh_turns)
        agent.marks_changed.connect(self.refresh_transcript)
        agent.budget_changed.connect(self._on_budget)
        agent.mode_changed.connect(lambda _mode: self._apply_mode())
        agent.settings.config_changed.connect(self._on_config)
        agent.settings.profiles.active_changed.connect(
            lambda _name: self._on_config(agent.settings.config)
        )
        agent.live.transcript_changed.connect(self._on_live_transcript)
        agent.live.state_changed.connect(self._on_live_state)
        agent.live.sources_changed.connect(self._on_sources)
        self._on_config(agent.settings.config)
        self._on_sources()
        self._on_state({})
        self._on_live_state({})
        self._on_budget()
        self._apply_mode()

    # -- Construcción ------------------------------------------

    def _build_header(self, toggle_run: Callable[[], None]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.status = StatusLine()
        row.addWidget(self.status, 1)
        self.panel_selector = SegmentedButtons(PANELS)
        self.panel_selector.select("agent")
        self.panel_selector.changed.connect(self.show_panel)
        self.panel_selector.setVisible(self.chat is not None)
        row.addWidget(self.panel_selector)
        self.mode_selector = SegmentedButtons(MODES)
        self.mode_selector.select(self.agent.mode)
        self.mode_selector.changed.connect(self._on_mode)
        row.addWidget(self.mode_selector)
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
        self.hint = QLabel(HINT)
        set_tone(self.hint, Tone.MUTED)
        row.addWidget(self.hint)
        row.addStretch(1)
        self.context_bar = ContextBar()
        row.addWidget(self.context_bar)
        row.addSpacing(8)
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

    @property
    def panel(self) -> str:
        return "chat" if self.right.currentWidget() is self.chat_panel else "agent"

    def show_panel(self, panel: str) -> None:
        """Cambia la columna derecha; sin chat, siempre el agente."""
        if panel == "chat" and self.chat_panel is not None:
            self.right.setCurrentWidget(self.chat_panel)
            self.chat_panel.input.setFocus()
        else:
            self.right.setCurrentIndex(0)
        self.panel_selector.select(self.panel)
        self.panel_changed.emit(self.panel)

    def _on_mode(self, mode: str) -> None:
        self.agent.set_mode(mode)

    def _apply_mode(self) -> None:
        mode = self.agent.mode
        self.mode_selector.select(mode)
        for index, stretch in enumerate(STRETCH[mode]):
            self.columns.setStretch(index, stretch)
        self.hint.setText(HINT_AHEAD if mode == AHEAD else HINT)
        self.first_text_label.setToolTip(FIRST_TEXT_TIPS[mode])
        self.refresh_theme()

    def _on_speaker(self, source: str) -> None:
        self.agent.set_speaker(source)
        self.refresh_transcript()

    def _on_live_transcript(self, source: str) -> None:
        if source == self.agent.speaker:
            self.refresh_transcript()

    # -- Señales -----------------------------------------------

    def _on_state(self, payload: dict) -> None:
        logic = self.agent.logic
        self.status.set_status(self.agent.status, STATE_TONES[logic.state])
        self.cancel_button.setEnabled(logic.state in (AgentState.START_MARKED, AgentState.SENDING))
        self.speaker_selector.setEnabled(logic.state is not AgentState.SENDING)

    def _on_live_state(self, payload: dict) -> None:
        live = self.agent.live.logic
        self.run_button.setText("Detener" if live.can_stop else "Iniciar")
        set_role(self.run_button, ButtonRole.DANGER if live.can_stop else ButtonRole.PRIMARY)
        self.run_button.setEnabled(live.can_stop or live.can_start)

    def _on_sources(self) -> None:
        """Solo un canal abierto se ofrece como interlocutor (el coordinador ya cambió el suyo)."""
        for segment in SPEAKERS:
            is_open = segment.key not in self.agent.live.closed_sources
            button = self.speaker_selector.buttons[segment.key]
            button.setEnabled(is_open)
            button.setToolTip(segment.tip if is_open else "Canal cerrado en Transcripción")
        self.speaker_selector.select(self.agent.speaker)
        self.refresh_transcript()

    def _on_budget(self) -> None:
        self.context_bar.set_budget(self.agent.budget)
        self._refresh_first_text()

    def _refresh_first_text(self) -> None:
        budget = self.agent.budget
        cached = budget.cached_fraction if budget is not None else None
        self.first_text_label.setText(first_text(self.agent.last_first_text_s, cached))

    def _on_config(self, config: ClaudeModelConfig) -> None:
        self.config_label.setText(config_text(config, self.agent.settings.profiles.active))
        self.config_label.setToolTip(config_tip(config))

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
        render = ahead_html if self.agent.mode == AHEAD else turns_html
        keep_scroll(self.turns_view, render(self.agent.turns, tokens(), mono_font().family()))
        self._refresh_first_text()

    def refresh_theme(self) -> None:
        self.refresh_transcript()
        self.refresh_turns()
        self.context_bar.refresh_theme()
        if self.chat_panel is not None:
            self.chat_panel.refresh()
