"""
Panel de contexto del agente (módulo Configuración).

Las rutas van una por línea, escritas o agregadas con los botones; Recargar rehace la
foto `contexto.md` y Abrir la deja revisar o corregir a mano. Solo habla con
`AgentContext`.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from coordinator_context import AgentContext
from ui.blocks.panel import titled_panel
from ui.blocks.status_line import StatusLine
from ui.theme import ButtonRole, Tone, mono_font, set_role, set_tone

LEVEL_TONES = {
    "ok": Tone.OK,
    "warning": Tone.WARNING,
    "info": Tone.INFO,
    "error": Tone.ERROR,
    "busy": Tone.INFO,
}
PATHS_HINT = "Una ruta por línea: archivos o carpetas con información de la empresa"
HELP_TEXT = (
    "IvyBells lee texto (md, txt, csv, json, código), PDF y Word (.docx); audio, video y el "
    "resto de Office quedan fuera. Es una foto: se rehace con Recargar, no en cada envío."
)
PATHS_HEIGHT = 96
# Espera tras la última tecla antes de guardar las rutas.
SAVE_DELAY_MS = 800


def pick_files(parent: QWidget) -> list[str]:
    files, _filter = QFileDialog.getOpenFileNames(parent, "Agregar archivos de contexto")
    return files


def pick_folder(parent: QWidget) -> str:
    return QFileDialog.getExistingDirectory(parent, "Agregar carpeta de contexto")


class ContextEditor(QWidget):
    def __init__(self, context: AgentContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build())
        self._save_timer = QTimer(self, singleShot=True, interval=SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._save_paths)
        context.paths_changed.connect(self._show_paths)
        context.reloaded.connect(self._on_reloaded)
        self._show_paths()
        self._refresh_open()

    # -- Construcción ------------------------------------------

    def _build(self) -> QFrame:
        frame, layout = titled_panel("files", "Contexto de la empresa")
        self.paths_edit = QPlainTextEdit()
        self.paths_edit.setFont(mono_font())
        self.paths_edit.setPlaceholderText(PATHS_HINT)
        self.paths_edit.setAccessibleName("Rutas de contexto")
        self.paths_edit.setFixedHeight(PATHS_HEIGHT)
        self.paths_edit.textChanged.connect(lambda: self._save_timer.start())
        layout.addWidget(self.paths_edit)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.add_files_button = self._button("Agregar archivos", self._on_add_files)
        self.add_folder_button = self._button("Agregar carpeta", self._on_add_folder)
        self.remove_button = self._button("Quitar ruta", self._on_remove)
        for button in (self.add_files_button, self.add_folder_button, self.remove_button):
            row.addWidget(button)
        row.addStretch(1)
        self.open_button = self._button("Abrir contexto.md", self._on_open)
        row.addWidget(self.open_button)
        self.reload_button = self._button("Recargar", self._on_reload, ButtonRole.PRIMARY)
        row.addWidget(self.reload_button)
        layout.addLayout(row)

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

    def _on_add_files(self) -> None:
        self._save_paths()
        self.context.add(pick_files(self))

    def _on_add_folder(self) -> None:
        folder = pick_folder(self)
        self._save_paths()
        if folder:
            self.context.add([folder])

    def _on_remove(self) -> None:
        """Quita la línea donde está el cursor."""
        cursor = self.paths_edit.textCursor()
        line = cursor.block().text().strip()
        self._save_paths()
        self.context.set_paths([path for path in self.context.paths if path != line])

    def _on_open(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.target)))

    def _on_reload(self) -> None:
        self._save_paths()
        self.context.reload()

    def _on_reloaded(self, payload: dict) -> None:
        self.status.set_status(payload["text"], LEVEL_TONES.get(payload["level"]))
        self.reload_button.setEnabled(payload["level"] != "busy")
        self._refresh_open()

    # -- Internos ----------------------------------------------

    def _lines(self) -> list[str]:
        return self.paths_edit.toPlainText().splitlines()

    def _save_paths(self) -> None:
        self._save_timer.stop()
        self.context.set_paths(self._lines())

    def _show_paths(self) -> None:
        """Pone las rutas guardadas sin pisar lo que el autor está escribiendo."""
        if [line.strip() for line in self._lines() if line.strip()] == self.context.paths:
            return
        self.paths_edit.blockSignals(True)
        self.paths_edit.setPlainText("\n".join(self.context.paths))
        self.paths_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.paths_edit.blockSignals(False)

    def _refresh_open(self) -> None:
        self.open_button.setEnabled(self.context.target.is_file())
