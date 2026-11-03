"""
Panel de contexto del agente (módulo Configuración).

El autor elige un contexto con nombre (una carpeta de `resources/agent/contextos/`)
en la lista; elegirlo rehace la foto `contexto.md`. Nuevo crea la carpeta y la abre para
llenarla, Renombrar le cambia el nombre, Abrir carpeta la muestra en el explorador,
Recargar rehace la foto tras cambiar archivos y Abrir contexto.md la deja revisar a mano.
Debajo, lo que pesa cada archivo en la foto. Solo habla con `AgentContext`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from coordinator_context import NEW_NAME, AgentContext
from core.context_budget import format_tokens
from ui.blocks.panel import titled_panel
from ui.blocks.status_line import StatusLine
from ui.theme import ButtonRole, Tone, set_role, set_tone

LEVEL_TONES = {
    "ok": Tone.OK,
    "warning": Tone.WARNING,
    "info": Tone.INFO,
    "error": Tone.ERROR,
    "busy": Tone.INFO,
}
NO_CONTEXT = "Sin contexto"
HELP_TEXT = (
    "Cada contexto es una carpeta de resources/agent/contextos: pon ahí los archivos y pulsa "
    "Recargar. IvyBells lee texto (md, txt, csv, json, código), PDF y Word (.docx); audio, "
    "video y el resto de Office quedan fuera. Es una foto: no se rehace en cada envío."
)


def weights_text(weights: dict[str, int]) -> str:
    """ "Peso en contexto.md: empresa ~4,2 k, manual.txt 0 (sin leer)"."""
    if not weights:
        return ""
    shown = [
        f"{Path(path).name or path} ~{format_tokens(tokens)}"
        if tokens
        else f"{Path(path).name or path} 0 (sin leer o vacío)"
        for path, tokens in weights.items()
    ]
    return "Peso en contexto.md (tokens): " + ", ".join(shown)


def ask_name(parent: QWidget, title: str, current: str) -> str | None:
    """El nombre que escribe el autor, o None si cancela."""
    text, ok = QInputDialog.getText(parent, title, "Nombre:", text=current)
    return text if ok else None


def open_folder(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class ContextEditor(QWidget):
    def __init__(self, context: AgentContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build())
        context.contexts_changed.connect(self._fill_combo)
        context.active_changed.connect(lambda _name: self._fill_combo())
        context.reloaded.connect(self._on_reloaded)
        self._fill_combo()
        self._refresh_open()

    # -- Construcción ------------------------------------------

    def _build(self) -> QFrame:
        frame, layout = titled_panel("files", "Contexto de la empresa")
        row = QHBoxLayout()
        row.setSpacing(6)
        self.combo = QComboBox()
        self.combo.setAccessibleName("Contexto en uso")
        self.combo.setMinimumContentsLength(24)
        self.combo.activated.connect(self._on_chosen)
        row.addWidget(self.combo, 1)
        self.new_button = self._button("Nuevo", self._on_new)
        self.rename_button = self._button("Renombrar", self._on_rename)
        self.folder_button = self._button("Abrir carpeta", self._on_open_folder)
        for button in (self.new_button, self.rename_button, self.folder_button):
            row.addWidget(button)
        layout.addLayout(row)

        self.weights_label = QLabel()
        self.weights_label.setWordWrap(True)
        set_tone(self.weights_label, Tone.MUTED)
        layout.addWidget(self.weights_label)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addStretch(1)
        self.open_button = self._button("Abrir contexto.md", self._on_open)
        actions.addWidget(self.open_button)
        self.reload_button = self._button("Recargar", self._on_reload, ButtonRole.PRIMARY)
        actions.addWidget(self.reload_button)
        layout.addLayout(actions)

        self.status = StatusLine()
        layout.addWidget(self.status)
        help_label = QLabel(HELP_TEXT)
        help_label.setWordWrap(True)
        set_tone(help_label, Tone.MUTED)
        layout.addWidget(help_label)
        return frame

    def _button(self, text: str, slot, role: ButtonRole = ButtonRole.SECONDARY) -> QPushButton:
        button = QPushButton(text)
        set_role(button, role)
        button.clicked.connect(slot)
        return button

    # -- Eventos -----------------------------------------------

    def _on_chosen(self, index: int) -> None:
        self.context.set_active(self.combo.itemData(index) or "")

    def _on_new(self) -> None:
        name = ask_name(self, "Nuevo contexto", NEW_NAME)
        if name is None:
            return
        created = self.context.create(name)
        if created and self.context.folder is not None:
            open_folder(self.context.folder)

    def _on_rename(self) -> None:
        current = self.context.active
        name = ask_name(self, "Renombrar contexto", current)
        if name is not None and current:
            self.context.rename(current, name)

    def _on_open_folder(self) -> None:
        if self.context.folder is not None:
            open_folder(self.context.folder)

    def _on_open(self) -> None:
        open_folder(self.context.target)

    def _on_reload(self) -> None:
        self.context.reload()

    def _on_reloaded(self, payload: dict) -> None:
        self.status.set_status(payload["text"], LEVEL_TONES.get(payload["level"]))
        self.reload_button.setEnabled(payload["level"] != "busy")
        self._refresh_open()
        if payload["level"] != "busy":
            self._refresh_weights()

    # -- Internos ----------------------------------------------

    def _fill_combo(self) -> None:
        active = self.context.active
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(NO_CONTEXT, "")
        for name in self.context.names():
            self.combo.addItem(name, name)
        self.combo.setCurrentIndex(max(self.combo.findData(active), 0))
        self.combo.blockSignals(False)
        self.rename_button.setEnabled(bool(active))
        self.folder_button.setEnabled(bool(active))
        self._refresh_weights()

    def _refresh_weights(self) -> None:
        text = weights_text(self.context.weights())
        self.weights_label.setText(text)
        self.weights_label.setVisible(bool(text))

    def _refresh_open(self) -> None:
        self.open_button.setEnabled(self.context.target.is_file())
