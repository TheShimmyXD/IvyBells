"""
Ventana principal: la barra con tres módulos (Transcripción, Agente y Configuración).

Es la raíz de composición: recibe la escucha en vivo y crea (si no se los pasan) la
configuración de Claude, el coordinador del Agente y el del chat propio; cada página
solo habla con los suyos.
Los tres comparten la misma escucha: cambiar de módulo no la detiene. Lo que el autor
elige (tema, modelo de transcripción, fuentes, interlocutor y módulo) llega en `prefs` y
cada cambio sale por `remember(clave, valor)`; la ventana no escribe la configuración.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from PySide6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QWidget

from coordinator_agent import AgentCoordinator
from coordinator_chat import ChatCoordinator
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
        remember: Callable[[str, object], object] | None = None,
        agent: AgentCoordinator | None = None,
        prefs: dict | None = None,
        chat: ChatCoordinator | None = None,
    ) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.agent = agent or AgentCoordinator(coordinator, ClaudeSettings(), parent=self)
        self.chat = chat or ChatCoordinator(coordinator, self.agent.settings, parent=self)
        self._fonts = fonts
        self._theme = theme
        # Las capturas y las pruebas no pasan ninguno: no escriben la configuración.
        self._remember = remember
        prefs = prefs or {}
        self.agent.set_speaker(prefs.get("speaker", self.agent.speaker))
        self.agent.set_mode(prefs.get("agent_mode", self.agent.mode))
        self._apply_theme()
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(app_icon())
        self._build_ui(prefs)
        self.show_module(prefs.get("module", "live"))
        self._connect_prefs()
        self.setMinimumSize(*MIN_SIZE)
        self.resize(*WINDOW_SIZE)

    # -- Construcción ------------------------------------------

    def _build_ui(self, prefs: dict) -> None:
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

        self.live_page = LivePage(self.coordinator, prefs.get("devices"))
        if prefs.get("live_model"):
            self.live_page.model_selector.select(prefs["live_model"])
        self.agent_page = AgentPage(self.agent, self.live_page.toggle_run, self.chat)
        self.agent_page.show_panel(prefs.get("agent_panel", "agent"))
        self.config_page = ClaudeConfigPage(self.agent.settings, self.agent)
        self.pages = {"live": self.live_page, "agent": self.agent_page, "config": self.config_page}
        self.stack = QStackedWidget()
        for page in self.pages.values():
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

    def _connect_prefs(self) -> None:
        # Después de aplicar las guardadas: solo cuenta lo que el autor cambia.
        self.sidebar.module_chosen.connect(lambda module: self._save("module", module))
        self.live_page.model_selector.changed.connect(lambda model: self._save("live_model", model))
        self.live_page.devices_chosen.connect(lambda devices: self._save("devices", devices))
        self.coordinator.sources_changed.connect(
            lambda: self._save("closed_sources", sorted(self.coordinator.closed_sources))
        )
        self.agent_page.speaker_selector.changed.connect(
            lambda speaker: self._save("speaker", speaker)
        )
        self.agent_page.mode_selector.changed.connect(lambda mode: self._save("agent_mode", mode))
        self.agent_page.panel_changed.connect(lambda panel: self._save("agent_panel", panel))

    def _save(self, key: str, value: object) -> None:
        if self._remember is not None:
            self._remember(key, value)

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
        self._save("theme", self._theme)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._apply_theme()
        self.sidebar.refresh_theme()
        self.sidebar.set_item("theme", THEME_TIPS[theme], THEME_GLYPHS[theme])
        self.live_page.refresh_theme()
        self.agent_page.refresh_theme()
        self.config_page.refresh_theme()

    # -- Eventos de Qt -----------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        super().resizeEvent(event)
        self.sidebar.place(0, 0, self.height())
        self.sidebar.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self.agent.close()
        self.chat.close()
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
    from coordinator_context import AgentContext
    from coordinator_profiles import AgentProfiles
    from paths import AGENT_PROFILE_LOCAL
    from services.service_profiles import ProfileStore

    app = QApplication.instance() or QApplication(sys.argv)
    config = load_app_config()

    def remember(key: str, value: object) -> None:
        setattr(config, key, value)
        save_app_config(config)

    prefs = {
        "live_model": config.live_model,
        "devices": config.devices,
        "speaker": config.speaker,
        "agent_mode": config.agent_mode,
        "agent_panel": config.agent_panel,
        "module": config.module,
    }
    store = ProfileStore()
    store.adopt_legacy(AGENT_PROFILE_LOCAL)
    profiles = AgentProfiles(
        store, config.agent_profile, lambda name: remember("agent_profile", name)
    )
    context = AgentContext(config.agent_context, lambda name: remember("agent_context", name))
    live = LiveCoordinator(closed_sources=config.closed_sources)
    agent = AgentCoordinator(
        live,
        ClaudeSettings(
            config.claude,
            lambda claude: remember("claude", claude),
            profiles=profiles,
            context=context,
        ),
    )
    chat = ChatCoordinator(live, agent.settings, config.chat_model, config.chat_effort, remember)
    window = MainWindow(live, load_fonts(), config.theme, remember, agent, prefs, chat)
    window.show()
    logger.info("Ventana principal lista")
    sys.exit(app.exec())
