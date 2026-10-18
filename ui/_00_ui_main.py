"""
Ventana principal: la barra con tres módulos (Transcripción, Agente y Configuración).

Es la raíz de composición: recibe la escucha en vivo y crea (si no se los pasan) la
configuración de Claude y el coordinador del Agente; cada página solo habla con el suyo.
Los tres comparten la misma escucha: cambiar de módulo no la detiene.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from PySide6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QWidget

from coordinator_agent import AgentCoordinator
from coordinator_config import ClaudeSettings
from coordinator_live import LiveCoordinator
from ui._00_ui_sidebar import COLLAPSED_WIDTH, NavSidebar
from ui.agent_page import AgentPage
from ui.blocks.icons import set_icon_font
from ui.blocks.logo import app_icon
from ui.config_page import ClaudeConfigPage
from ui.live_page import LivePage
from ui.theme import ThemeFonts, apply_theme, next_theme, resolve_theme

logger = logging.getLogger(__name__)

WINDOW_TITLE = "IvyBells"
WINDOW_SIZE = (980, 600)
MIN_SIZE = (760, 460)
THEME_TIPS = {"light": "Tema: claro", "dark": "Tema: oscuro"}
THEME_GLYPHS = {"light": "sun", "dark": "moon"}
# (id, rótulo, icono, ayuda), en el orden de la barra.
MODULES = (
    ("live", "Transcripción", "waveform", "Ellos y Tú en vivo"),
    ("agent", "Agente", "robot", "Marca lo que dijo el cliente y responde Claude"),
    ("config", "Configuración", "sliders-horizontal", "Cuenta, modelo y esfuerzo de Claude"),
)


class MainWindow(QWidget):
    def __init__(
        self,
        coordinator: LiveCoordinator,
        fonts: ThemeFonts,
        theme: str = "light",
        save_theme: Callable[[str], object] | None = None,
        agent: AgentCoordinator | None = None,
    ) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.agent = agent or AgentCoordinator(coordinator, ClaudeSettings(), parent=self)
        self._fonts = fonts
        self._theme = theme
        # Las capturas y las pruebas no pasan ninguno: no escriben la configuración.
        self._save_theme = save_theme
        self._apply_theme()
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(app_icon())
        self._build_ui()
        self.show_module("live")
        self.setMinimumSize(*MIN_SIZE)
        self.resize(*WINDOW_SIZE)

    # -- Construcción ------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # La barra no va en el layout: desplegada pasa por encima del área de trabajo.
        self.sidebar = NavSidebar(self)
        for module in MODULES:
            self.sidebar.add_module(*module)
        self.sidebar.module_chosen.connect(self.show_module)
        self.theme_button = self.sidebar.add_action(
            "theme", THEME_TIPS[self._theme], THEME_GLYPHS[self._theme], self._cycle_theme
        )
        slot = QWidget()
        slot.setFixedWidth(COLLAPSED_WIDTH)
        root.addWidget(slot)

        self.live_page = LivePage(self.coordinator)
        self.agent_page = AgentPage(self.agent, self.live_page.toggle_run)
        self.config_page = ClaudeConfigPage(self.agent.settings)
        self.pages = {"live": self.live_page, "agent": self.agent_page, "config": self.config_page}
        self.stack = QStackedWidget()
        for page in self.pages.values():
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

    def show_module(self, module_id: str) -> None:
        if module_id not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[module_id])
        self.sidebar.buttons[module_id].setChecked(True)

    @property
    def current_module(self) -> str:
        return next(key for key, page in self.pages.items() if page is self.stack.currentWidget())

    def selected_devices(self) -> dict[str, str]:
        return self.live_page.selected_devices()

    # -- Tema --------------------------------------------------

    def _apply_theme(self) -> None:
        apply_theme(QApplication.instance(), self._fonts, resolve_theme(self._theme))

    def _cycle_theme(self) -> None:
        self.set_theme(next_theme(self._theme))
        if self._save_theme is not None:
            self._save_theme(self._theme)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._apply_theme()
        self.sidebar.refresh_theme()
        self.sidebar.set_item("theme", THEME_TIPS[theme], THEME_GLYPHS[theme])
        self.live_page.refresh_theme()
        self.agent_page.refresh_theme()

    # -- Eventos de Qt -----------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        super().resizeEvent(event)
        self.sidebar.place(0, 0, self.height())
        self.sidebar.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self.agent.close()
        self.agent.settings.close()
        self.coordinator.close()
        super().closeEvent(event)


def load_fonts() -> ThemeFonts:
    """Registra las letras y los iconos del tema; la UI no lee archivos."""
    from managers.app_fonts import load_app_fonts
    from managers.icon_font import load_icon_font

    set_icon_font(*load_icon_font())
    return ThemeFonts(*load_app_fonts())


def run_app() -> None:
    from config import load_app_config, save_app_config

    app = QApplication.instance() or QApplication(sys.argv)
    config = load_app_config()

    def save_theme(theme: str) -> None:
        config.theme = theme
        save_app_config(config)

    def save_claude(claude) -> None:
        config.claude = claude
        save_app_config(config)

    live = LiveCoordinator()
    agent = AgentCoordinator(live, ClaudeSettings(config.claude, save_claude))
    window = MainWindow(live, load_fonts(), config.theme, save_theme, agent)
    window.show()
    logger.info("Ventana principal lista")
    sys.exit(app.exec())
