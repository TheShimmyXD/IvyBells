"""
Capturas de la ventana real en sus estados, en los temas claro y oscuro.

    QT_QPA_PLATFORM=offscreen .venv/bin/python captura_ui.py <carpeta>

Usa un coordinador sin hilo ni GPU y frases de ejemplo (nunca de una llamada real);
las señales del worker se llaman a mano. Los PNG no se versionan.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from coordinator_agent import AgentCoordinator
from coordinator_live import DEFAULT_MODEL, LiveCoordinator
from core.claude_account import AccountStatus
from core.claude_model import ClaudeModelConfig
from core.engine import TranscriptEvent
from services.service_pipewire import AudioSource, CaptureSources, SourceChoices

MONITOR = AudioSource(48, "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor", "PipeWire", "", "")
MICROPHONE = AudioSource(49, "alsa_input.pci-0000_0d_00.4.analog-stereo", "PipeWire", "", "")
STARTED = datetime(2026, 10, 17, 18, 5, 0)
# (fuente, segundo de inicio, texto, es final)
SAMPLE_EVENTS = (
    ("ellos", 31.0, "Buenas tardes a todos, ¿me escuchan bien?", True),
    ("ellos", 34.0, "Queremos ver cómo va la transcripción con el equipo nuevo.", True),
    ("tu", 41.0, "Sí, perfecto. Empiezo compartiendo la pantalla.", True),
    ("tu", 52.0, "Todo corre en la GPU de la oficina, sin mandar el audio a la nube.", True),
    ("ellos", 63.0, "¿Y cuánto tarda en aparecer el texto después de que uno habla?", True),
    ("tu", 69.0, "Menos de dos segundos desde que termino la frase, y mientras", False),
)
SAMPLE_LATENCY = (1.62, 1.78)
SAMPLE_ERROR = "No se pudo abrir la fuente analog-stereo.monitor"
STATES = ("detenido", "escuchando", "error")
THEMES = ("light", "dark")
# Módulo Agente: lo que dice un cliente de ejemplo ("ellos") y las respuestas de ejemplo.
AGENT_EVENTS = (
    (2.0, "Buenas tardes, ¿hablo con soporte?"),
    (6.0, "Sí, mire, contraté el plan empresarial la semana pasada"),
    (11.0, "y todavía no me llega la factura al correo."),
    (17.0, "¿Me pueden decir cuándo la envían y si puedo pagar con transferencia?"),
)
AGENT_PARTIAL = (25.0, "Ah, y otra cosa")
AGENT_ANSWERS = (
    "Buenas tardes, sí, habla con el asistente de soporte. ¿En qué le puedo ayudar?",
    "Entiendo, gracias por avisarnos. La factura del plan empresarial se envía en los "
    "primeros cinco días hábiles después de la contratación, y sí puede pagar",
)
AGENT_ERROR = "Claude no respondió en 120 s"
AGENT_STATES = ("sin_seleccion", "inicio", "enviando", "error")
# Página Configuración: (estado, cuenta escrita, lo que diría `claude auth status`).
# (estado, cuenta, estado de la cuenta, perfil abierto en el editor)
CONFIG_STATES = (
    (
        "con_sesion",
        "persona@example.com",
        AccountStatus(True, "persona@example.com", "pro"),
        "demo soporte",
    ),
    ("sin_sesion", "otra@example.com", AccountStatus(False), "ejemplo"),
)
SAMPLE_PROFILE = (
    "Eres el asistente de soporte técnico de una empresa de ejemplo.\n\n"
    "Cómo respondes:\n"
    "- Con calma y en frases cortas: la respuesta se lee en voz alta.\n"
    "- Primero confirmas qué entendiste del problema y luego das un solo paso a seguir.\n\n"
    "Datos de la empresa:\n"
    "- Soporte de lunes a sábado, de 7:00 a 20:00.\n"
)


class PreviewCoordinator(LiveCoordinator):
    """El coordinador real sin lanzar el worker ni consultar PipeWire."""

    def read_sources(self) -> SourceChoices:
        return SourceChoices([MONITOR], [MICROPHONE], CaptureSources(MONITOR, MICROPHONE))

    def _launch(self, model: str, devices: dict[str, str]) -> None:
        pass


class PreviewAgent(AgentCoordinator):
    """El coordinador real del Agente sin lanzar la CLI: las respuestas se dan a mano."""

    def _launch(self, prompt: str) -> None:
        self._requests.next()

    def answer(self, text: str, done: bool = True, error: str = "") -> None:
        for chunk in text.split(" "):
            self.on_text(chunk + " ")
        if error:
            self.on_failed(error)
        if done or error:
            self.on_finished({"_request_id": self._requests._current, "answer": text})


def _play_listening(coordinator: PreviewCoordinator, devices: dict[str, str]) -> None:
    coordinator.start(DEFAULT_MODEL, devices)
    coordinator.on_loaded(STARTED)
    for source, start_s, text, is_final in SAMPLE_EVENTS:
        coordinator.on_event(TranscriptEvent(source, is_final, text, start_s, start_s + 3.0))
    coordinator.on_latency(*SAMPLE_LATENCY)


def capture_states(out_dir: Path) -> list[Path]:
    """Guarda `ventana_<estado>_<tema>.png` en `out_dir` y devuelve las rutas."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ui._00_ui_main import MainWindow, load_fonts

    app = QApplication.instance() or QApplication([])
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()
    paths = []
    for theme in THEMES:
        for state in STATES:
            coordinator = PreviewCoordinator()
            window = MainWindow(coordinator, fonts, theme)
            if state in ("escuchando", "error"):
                _play_listening(coordinator, window.selected_devices())
            if state == "error":
                coordinator.on_failed(SAMPLE_ERROR)
            window.show()
            app.processEvents()
            path = out_dir / f"ventana_{state}_{theme}.png"
            window.grab().save(str(path))
            paths.append(path)
            window.close()
    return paths


def _sample_context(folder: Path) -> list[str]:
    """Archivos de ejemplo para el panel de contexto (nunca los del autor)."""
    folder.mkdir()
    (folder / "servicios.md").write_text("# Servicios\n\n- Plan básico\n", encoding="utf-8")
    (folder / "precios.csv").write_text("plan,precio\nbásico,10\n", encoding="utf-8")
    (folder / "precios.xlsx").write_bytes(b"PK")
    return [str(folder), str(folder.parent / "manual_no_existe.txt")]


def capture_config(out_dir: Path) -> list[Path]:
    """
    Guarda `config_<estado>_<tema>.png`; las carpetas de cuentas y los perfiles van a un
    temporal (nunca se muestra el perfil real de la empresa).
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from coordinator_config import ClaudeSettings
    from coordinator_context import AgentContext
    from coordinator_profiles import AgentProfiles
    from paths import AGENT_PROFILES_DIR
    from services.service_profiles import ProfileStore
    from ui._00_ui_main import load_fonts
    from ui.config_page import ClaudeConfigPage
    from ui.theme import apply_theme, resolve_theme

    app = QApplication.instance() or QApplication([])
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()
    paths = []
    with (
        tempfile.TemporaryDirectory(prefix="ivybells_cuentas_") as accounts,
        tempfile.TemporaryDirectory(prefix="ivybells_perfiles_") as folder,
    ):
        store = ProfileStore(Path(folder))
        store.create("ejemplo", (AGENT_PROFILES_DIR / "ejemplo.md").read_text(encoding="utf-8"))
        store.create("demo soporte", SAMPLE_PROFILE)
        sample_paths = _sample_context(Path(folder) / "empresa")
        for theme in THEMES:
            apply_theme(app, fonts, resolve_theme(theme))
            for state, account, status, opened in CONFIG_STATES:
                config = ClaudeModelConfig(model="sonnet", effort="high", account=account)
                profiles = AgentProfiles(store, "demo soporte")
                context = AgentContext(
                    sample_paths, target=Path(folder) / "contexto" / "contexto.md"
                )
                settings = ClaudeSettings(
                    config, accounts_dir=Path(accounts), profiles=profiles, context=context
                )
                page = ClaudeConfigPage(settings)
                settings.show_status(status)
                page.profile_editor.select(opened)
                context.reload()
                while context.is_busy():
                    app.processEvents()
                page.resize(900, 1060)
                page.show()
                app.processEvents()
                path = out_dir / f"config_{state}_{theme}.png"
                page.grab().save(str(path))
                paths.append(path)
                page.close()
    return paths


def _play_agent(coordinator: PreviewCoordinator, agent: PreviewAgent, state: str) -> None:
    coordinator.start(DEFAULT_MODEL, {"ellos": MONITOR.name})
    coordinator.on_loaded(STARTED)
    for start_s, text in AGENT_EVENTS:
        coordinator.on_event(TranscriptEvent("ellos", True, text, start_s, start_s + 3.0))
    start_s, text = AGENT_PARTIAL
    coordinator.on_event(TranscriptEvent("ellos", False, text, start_s, start_s + 1.0))
    if state == "sin_seleccion":
        return
    agent.mark_start(0, 0)
    agent.mark_end(0, 99)
    agent.answer(AGENT_ANSWERS[0])
    agent.mark_start(1, 4)  # "mire,"
    if state == "inicio":
        return
    agent.mark_end(3, 80)
    agent.answer(AGENT_ANSWERS[1], done=False, error=AGENT_ERROR if state == "error" else "")


def capture_agent(out_dir: Path) -> list[Path]:
    """Guarda `agente_<estado>_<tema>.png` (ventana real en el módulo Agente)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from coordinator_config import ClaudeSettings
    from ui._00_ui_main import MainWindow, load_fonts

    app = QApplication.instance() or QApplication([])
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()
    paths = []
    for theme in THEMES:
        for state in AGENT_STATES:
            coordinator = PreviewCoordinator()
            settings = ClaudeSettings(ClaudeModelConfig(model="sonnet", effort="high"))
            agent = PreviewAgent(coordinator, settings)
            window = MainWindow(coordinator, fonts, theme, agent=agent)
            window.show_module("agent")
            _play_agent(coordinator, agent, state)
            window.show()
            app.processEvents()
            path = out_dir / f"agente_{state}_{theme}.png"
            window.grab().save(str(path))
            paths.append(path)
            window.close()
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: captura_ui.py <carpeta>")
    out = Path(sys.argv[1])
    for saved in [*capture_states(out), *capture_agent(out), *capture_config(out)]:
        sys.stdout.write(f"{saved}\n")
