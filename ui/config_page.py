"""
Página Configuración: con qué cuenta y qué modelo responde Claude en el módulo Agente.

Arriba la cuenta (correo, Comprobar y, si hace falta, la orden para iniciar sesión);
después el modelo, el esfuerzo, el respaldo y el tiempo máximo; abajo los perfiles del
agente (`ProfileEditor`) y su contexto (`ContextEditor`). Solo habla con `ClaudeSettings`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from coordinator_config import CLAUDE_MODELS, EFFORTS, FALLBACKS, TIMEOUTS_S, ClaudeSettings
from ui.blocks.panel import titled_panel
from ui.blocks.segmented import Segment, SegmentedButtons
from ui.blocks.status_line import StatusLine
from ui.context_editor import ContextEditor
from ui.profile_editor import ProfileEditor
from ui.theme import ButtonRole, Tone, mono_font, set_role, set_tone

LEVEL_TONES = {"ok": Tone.OK, "warning": Tone.WARNING, "error": Tone.ERROR, "busy": Tone.INFO}
ACCOUNT_HINT = "Correo de la cuenta de Claude; vacío = la sesión de siempre"
LOGIN_HINT = (
    "Pega esta orden en una terminal: abre el navegador y luego pide pegar un código. "
    "Después vuelve y pulsa Comprobar."
)


def _muted(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    set_tone(label, Tone.MUTED)
    return label


class ClaudeConfigPage(QWidget):
    def __init__(self, settings: ClaudeSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        # En una ventana baja la página se desplaza en vez de aplastar el editor del perfil.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        layout.addWidget(self._build_account())
        layout.addWidget(self._build_answer())
        self.profile_editor = ProfileEditor(settings.profiles)
        layout.addWidget(self.profile_editor, 1)
        self.context_editor = ContextEditor(settings.context)
        layout.addWidget(self.context_editor)
        settings.account_checked.connect(self._on_account_checked)
        settings.config_changed.connect(lambda _config: self._refresh())
        self._refresh()
        self._on_account_checked({"text": "", "level": "", "login": ""})

    # -- Construcción ------------------------------------------

    def _build_account(self) -> QFrame:
        frame, layout = titled_panel("user-circle", "Cuenta")
        row = QHBoxLayout()
        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText(ACCOUNT_HINT)
        self.account_edit.setAccessibleName("Cuenta de Claude")
        self.account_edit.editingFinished.connect(self._on_account_edited)
        row.addWidget(self.account_edit, 1)
        self.check_button = QPushButton("Comprobar")
        set_role(self.check_button, ButtonRole.SECONDARY)
        self.check_button.clicked.connect(self._on_check_clicked)
        row.addWidget(self.check_button)
        layout.addLayout(row)
        self.account_status = StatusLine()
        layout.addWidget(self.account_status)

        self.login_box = QWidget()
        login = QVBoxLayout(self.login_box)
        login.setContentsMargins(0, 0, 0, 0)
        login.setSpacing(4)
        login_row = QHBoxLayout()
        self.login_edit = QLineEdit()
        self.login_edit.setReadOnly(True)
        self.login_edit.setFont(mono_font())
        self.login_edit.setAccessibleName("Orden para iniciar sesión")
        login_row.addWidget(self.login_edit, 1)
        self.copy_button = QPushButton("Copiar")
        set_role(self.copy_button, ButtonRole.SECONDARY)
        self.copy_button.clicked.connect(self._on_copy_clicked)
        login_row.addWidget(self.copy_button)
        login.addLayout(login_row)
        login.addWidget(_muted(LOGIN_HINT))
        layout.addWidget(self.login_box)
        return frame

    def _build_answer(self) -> QFrame:
        frame, layout = titled_panel("sliders-horizontal", "Respuesta")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.model_selector = SegmentedButtons([Segment(*model) for model in CLAUDE_MODELS])
        self.model_selector.changed.connect(self.settings.set_model)
        form.addRow("Modelo", self.model_selector)
        self.effort_selector = SegmentedButtons([Segment(*effort) for effort in EFFORTS])
        self.effort_selector.changed.connect(self.settings.set_effort)
        form.addRow("Esfuerzo", self.effort_selector)
        self.fallback_box = QComboBox()
        self.fallback_box.setMinimumContentsLength(10)
        for model in FALLBACKS:
            self.fallback_box.addItem(model or "ninguno", model)
        self.fallback_box.currentIndexChanged.connect(
            lambda _i: self.settings.set_fallback(self.fallback_box.currentData())
        )
        form.addRow("Respaldo", self.fallback_box)
        self.timeout_box = QComboBox()
        self.timeout_box.setMinimumContentsLength(10)
        for seconds in TIMEOUTS_S:
            self.timeout_box.addItem(f"{seconds} s", seconds)
        self.timeout_box.currentIndexChanged.connect(
            lambda _i: self.settings.set_timeout(self.timeout_box.currentData())
        )
        form.addRow("Tiempo máximo", self.timeout_box)
        layout.addLayout(form)
        return frame

    # -- Eventos -----------------------------------------------

    def _on_account_edited(self) -> None:
        if self.account_edit.text().strip().lower() != self.settings.config.account:
            self.settings.set_account(self.account_edit.text())

    def _on_check_clicked(self) -> None:
        if self.account_edit.text().strip().lower() != self.settings.config.account:
            self.settings.set_account(self.account_edit.text())
        else:
            self.settings.check()

    def _on_copy_clicked(self) -> None:
        QApplication.clipboard().setText(self.login_edit.text())
        self.copy_button.setText("Copiada")

    def _on_account_checked(self, payload: dict) -> None:
        self.account_status.set_status(payload["text"], LEVEL_TONES.get(payload["level"]))
        self.check_button.setEnabled(payload["level"] != "busy")
        self.login_edit.setText(payload["login"])
        # Desde el principio: lo que importa es la carpeta de la cuenta.
        self.login_edit.setCursorPosition(0)
        self.copy_button.setText("Copiar")
        self.login_box.setVisible(bool(payload["login"]))

    def _refresh(self) -> None:
        """Pone los controles como dice la configuración, sin volver a guardarla."""
        config = self.settings.config
        if not self.account_edit.hasFocus():
            self.account_edit.setText(config.account)
        for widget, value in (
            (self.model_selector, config.model),
            (self.effort_selector, config.effort),
        ):
            widget.blockSignals(True)
            widget.select(value)
            widget.blockSignals(False)
        for box, value in (
            (self.fallback_box, config.fallback_model),
            (self.timeout_box, config.timeout_s),
        ):
            box.blockSignals(True)
            index = box.findData(value)
            if index < 0:
                box.addItem(f"{value} s", value)
                index = box.count() - 1
            box.setCurrentIndex(index)
            box.blockSignals(False)
