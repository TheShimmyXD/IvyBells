"""
Panel del chat propio: ocupa la columna derecha del Agente cuando se elige "Chat".

Arriba, el modelo y el esfuerzo del chat (aparte del agente); en el centro, las peticiones
y las respuestas en Markdown; abajo, el cuadro para escribir (Enter envía, Mayús+Enter
salta de línea), Enviar o Cancelar, Vaciar y el primer texto de la última respuesta.
Solo habla con `ChatCoordinator`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QWidget,
)

from coordinator_chat import ChatCoordinator, ChatTurn
from coordinator_config import CLAUDE_MODELS, EFFORTS
from core.claude_model import ClaudeModelConfig
from ui.agent_view import keep_scroll
from ui.blocks.panel import titled_panel
from ui.blocks.segmented import Segment, SegmentedButtons
from ui.theme import ButtonRole, Tone, mono_font, set_role, set_tone

INPUT_LINES = 3
PLACEHOLDER = "Pídele algo sobre la conversación o el proyecto (Enter envía, Mayús+Enter salta)"
EMPTY_TEXT = (
    "*Chat sin perfil: ve el contexto del proyecto y lo que se ha dicho en los dos canales, "
    "no las respuestas del agente.*"
)


def _quoted(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())


def _turn_markdown(turn: ChatTurn) -> str:
    effort = turn.effort or "por defecto"
    head = f"**Tú** `{turn.clock}` · {turn.model}, {effort}\n\n{_quoted(turn.request)}"
    if turn.error:
        body = f"{turn.answer}\n\n**Error:** {turn.error}".strip()
    elif turn.cancelled:
        body = f"{turn.answer} *(cancelado)*".strip()
    elif not turn.done:
        body = f"{turn.answer} ..." if turn.answer else f"*Esperando a {turn.model}...*"
    else:
        body = turn.answer
    return f"{head}\n\n{body}"


def chat_markdown(turns: list[ChatTurn]) -> str:
    """Todo el chat en Markdown, separado por reglas; vacío, el aviso de qué ve el chat."""
    if not turns:
        return EMPTY_TEXT
    return "\n\n---\n\n".join(_turn_markdown(turn) for turn in turns)


def first_text(seconds: float | None) -> str:
    return (
        "Primer texto -" if seconds is None else f"Primer texto {seconds:.1f} s".replace(".", ",")
    )


class ChatInput(QPlainTextEdit):
    """
    Signals
    -------
    submitted() -> Enter sin Mayús.
    """

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if is_enter and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class ChatPanel(QWidget):
    def __init__(self, chat: ChatCoordinator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chat = chat
        self.model_selector = SegmentedButtons([Segment(*model) for model in CLAUDE_MODELS])
        self.model_selector.changed.connect(chat.set_model)
        self.effort_box = QComboBox()
        self.effort_box.setToolTip("Esfuerzo del chat (aparte del agente)")
        for key, label, _tip in EFFORTS:
            self.effort_box.addItem(label, key)
        self.effort_box.currentIndexChanged.connect(
            lambda index: chat.set_effort(self.effort_box.itemData(index))
        )
        extra = QWidget()
        extra_row = QHBoxLayout(extra)
        extra_row.setContentsMargins(0, 0, 0, 0)
        extra_row.setSpacing(6)
        extra_row.addWidget(self.model_selector)
        extra_row.addWidget(self.effort_box)
        frame, layout = titled_panel("chats", "Chat", extra)
        self.frame = frame

        self.messages = QTextBrowser()
        self.messages.setFrameShape(QFrame.Shape.NoFrame)
        self.messages.setOpenExternalLinks(True)
        self.messages.setAccessibleName("Chat con Claude")
        layout.addWidget(self.messages, 1)

        self.input = ChatInput()
        self.input.setPlaceholderText(PLACEHOLDER)
        self.input.setAccessibleName("Petición para el chat")
        line = self.input.fontMetrics().lineSpacing()
        self.input.setFixedHeight(line * INPUT_LINES + 16)
        self.input.submitted.connect(self._on_send)
        layout.addWidget(self.input)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.first_text_label = QLabel(first_text(None))
        self.first_text_label.setFont(mono_font())
        set_tone(self.first_text_label, Tone.MUTED)
        row.addWidget(self.first_text_label)
        row.addStretch(1)
        self.clear_button = QPushButton("Vaciar")
        set_role(self.clear_button, ButtonRole.SECONDARY)
        self.clear_button.clicked.connect(chat.clear)
        row.addWidget(self.clear_button)
        self.send_button = QPushButton()
        self.send_button.clicked.connect(self._on_button)
        row.addWidget(self.send_button)
        layout.addLayout(row)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        chat.turns_changed.connect(self.refresh)
        chat.sending_changed.connect(self._on_sending)
        chat.config_changed.connect(self._on_config)
        self._on_config(chat.config)
        self._on_sending(chat.sending)
        self.refresh()

    # -- Eventos -----------------------------------------------

    def _on_send(self) -> None:
        if self.chat.send(self.input.toPlainText()):
            self.input.clear()

    def _on_button(self) -> None:
        if self.chat.sending:
            self.chat.cancel()
        else:
            self._on_send()

    # -- Señales -----------------------------------------------

    def _on_sending(self, sending: bool) -> None:
        self.send_button.setText("Cancelar" if sending else "Enviar")
        set_role(self.send_button, ButtonRole.DANGER if sending else ButtonRole.PRIMARY)

    def _on_config(self, config: ClaudeModelConfig) -> None:
        self.model_selector.select(config.model)
        self.effort_box.blockSignals(True)
        self.effort_box.setCurrentIndex(max(0, self.effort_box.findData(config.effort)))
        self.effort_box.blockSignals(False)

    def refresh(self) -> None:
        keep_scroll(self.messages, chat_markdown(self.chat.turns), markdown=True)
        self.first_text_label.setText(first_text(self.chat.last_first_text_s))
