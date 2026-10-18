"""
Panel de perfiles del agente (módulo Configuración).

A la izquierda la lista, con el perfil en uso marcado, y los botones Nuevo, Duplicar,
Renombrar y Borrar; a la derecha el texto del perfil elegido, Guardar y Usar en el
Agente. El de ejemplo se ve pero no se cambia: se duplica. Solo habla con `AgentProfiles`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from coordinator_profiles import AgentProfiles
from ui.blocks.panel import titled_panel
from ui.blocks.status_line import StatusLine
from ui.theme import ButtonRole, Tone, set_role, set_tone

NOTICE_TONES = {"ok": Tone.OK, "error": Tone.ERROR}
ACTIVE_SUFFIX = "  (en uso)"
READ_ONLY_HINT = "Este perfil viene con IvyBells y no se cambia: duplícalo para editarlo."
EDITOR_HINT = (
    "Rol, tono y datos de la empresa. Las reglas de seguridad las pone IvyBells siempre, "
    "antes de este texto."
)
LIST_WIDTH = 210
# Alto mínimo del editor: lo que hace falta para leer un perfil corto sin desplazarse.
EDITOR_MIN_HEIGHT = 220


def ask_name(parent: QWidget, current: str) -> str | None:
    """El nombre nuevo que escribe el autor, o None si cancela."""
    text, ok = QInputDialog.getText(parent, "Renombrar perfil", "Nombre:", text=current)
    return text if ok else None


def confirm(parent: QWidget, title: str, text: str) -> bool:
    answer = QMessageBox.question(parent, title, text)
    return answer == QMessageBox.StandardButton.Yes


class ProfileEditor(QWidget):
    def __init__(self, profiles: AgentProfiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profiles = profiles
        self.current = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build())
        profiles.profiles_changed.connect(self._fill_list)
        profiles.active_changed.connect(lambda _name: self._fill_list())
        profiles.notice.connect(self._on_notice)
        self._fill_list()
        self.select(profiles.active)

    # -- Construcción ------------------------------------------

    def _build(self) -> QFrame:
        frame, layout = titled_panel("identification-card", "Perfil del agente")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.list = QListWidget()
        self.list.setFixedWidth(LIST_WIDTH)
        self.list.setAccessibleName("Perfiles del agente")
        self.list.currentItemChanged.connect(self._on_item_changed)
        grid.addWidget(self.list, 0, 0)

        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName("Texto del perfil")
        self.editor.setPlaceholderText(EDITOR_HINT)
        self.editor.setMinimumHeight(EDITOR_MIN_HEIGHT)
        self.editor.modificationChanged.connect(lambda _dirty: self._refresh_buttons())
        grid.addWidget(self.editor, 0, 1)

        buttons = QGridLayout()
        buttons.setSpacing(6)
        self.new_button = self._button("Nuevo", self._on_new)
        self.duplicate_button = self._button("Duplicar", self._on_duplicate)
        self.rename_button = self._button("Renombrar", self._on_rename)
        self.delete_button = self._button("Borrar", self._on_delete, ButtonRole.DANGER)
        for index, button in enumerate(
            (self.new_button, self.duplicate_button, self.rename_button, self.delete_button)
        ):
            buttons.addWidget(button, index // 2, index % 2)
        grid.addLayout(buttons, 1, 0, Qt.AlignmentFlag.AlignTop)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        row = QHBoxLayout()
        self.status = StatusLine()
        row.addWidget(self.status, 1)
        self.use_button = self._button("Usar en el Agente", self._on_use)
        row.addWidget(self.use_button)
        self.save_button = self._button("Guardar", self._on_save, ButtonRole.PRIMARY)
        row.addWidget(self.save_button)
        actions.addLayout(row)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        set_tone(self.hint, Tone.MUTED)
        actions.addWidget(self.hint)
        grid.addLayout(actions, 1, 1, Qt.AlignmentFlag.AlignTop)

        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        layout.addLayout(grid, 1)
        return frame

    def _button(self, text: str, slot, role: ButtonRole = ButtonRole.SECONDARY) -> QPushButton:
        button = QPushButton(text)
        set_role(button, role)
        button.clicked.connect(slot)
        return button

    # -- Pedidos -----------------------------------------------

    def select(self, name: str) -> None:
        """Muestra `name` en el editor (si existe)."""
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentRow(row)
                return

    @property
    def dirty(self) -> bool:
        return self.editor.document().isModified()

    # -- Eventos -----------------------------------------------

    def _on_item_changed(self, item: QListWidgetItem | None, previous) -> None:
        name = item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        if name == self.current:
            return
        self._keep_changes()
        self._load(name)

    def _on_new(self) -> None:
        self._keep_changes()
        self.select(self.profiles.create())

    def _on_duplicate(self) -> None:
        self._keep_changes()
        self.select(self.profiles.duplicate(self.current))

    def _on_rename(self) -> None:
        text = ask_name(self, self.current)
        if text is None:
            return
        self._keep_changes()
        renamed = self.profiles.rename(self.current, text)
        if renamed:
            self.current = renamed
            self._fill_list()
            self.select(renamed)

    def _on_delete(self) -> None:
        name = self.current
        if not confirm(self, "Borrar perfil", f"¿Borrar el perfil {name}? No se puede deshacer."):
            return
        self.editor.document().setModified(False)
        if self.profiles.delete(name):
            self.select(self.profiles.active)

    def _on_save(self) -> None:
        if self.profiles.save(self.current, self.editor.toPlainText()):
            self.editor.document().setModified(False)

    def _on_use(self) -> None:
        self._keep_changes()
        self.profiles.set_active(self.current)

    def _on_notice(self, payload: dict) -> None:
        self.status.set_status(payload["text"], NOTICE_TONES.get(payload["level"]))

    # -- Internos ----------------------------------------------

    def _keep_changes(self) -> None:
        """Si el perfil abierto tiene cambios sin guardar, pregunta si se guardan."""
        if not self.dirty or not self.profiles.is_editable(self.current):
            return
        if confirm(self, "Cambios sin guardar", f"¿Guardar los cambios de {self.current}?"):
            self.profiles.save(self.current, self.editor.toPlainText())
        self.editor.document().setModified(False)

    def _load(self, name: str) -> None:
        self.current = name
        self.editor.setPlainText(self.profiles.text(name))
        self.editor.setReadOnly(not self.profiles.is_editable(name))
        self.editor.document().setModified(False)
        self.status.set_status("")
        self._refresh_buttons()

    def _fill_list(self) -> None:
        active = self.profiles.active
        self.list.blockSignals(True)
        self.list.clear()
        for name in self.profiles.names():
            item = QListWidgetItem(name + (ACTIVE_SUFFIX if name == active else ""))
            item.setData(Qt.ItemDataRole.UserRole, name)
            if name == active:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.list.addItem(item)
        self.list.blockSignals(False)
        names = self.profiles.names()
        if self.current in names:
            self.select(self.current)
        elif names:
            self.list.setCurrentRow(0)
        else:
            self._load("")
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        name = self.current
        editable = self.profiles.is_editable(name)
        self.duplicate_button.setEnabled(bool(name))
        self.rename_button.setEnabled(editable)
        self.delete_button.setEnabled(editable)
        self.save_button.setEnabled(editable and self.dirty)
        self.use_button.setEnabled(bool(name) and name != self.profiles.active)
        self.hint.setText(READ_ONLY_HINT if name and not editable else EDITOR_HINT)
