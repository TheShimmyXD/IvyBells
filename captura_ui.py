"""
Capturas de la ventana real en sus estados, en los temas claro y oscuro.

    QT_QPA_PLATFORM=offscreen .venv/bin/python captura_ui.py <carpeta>

Usa un coordinador sin hilo ni GPU y frases de ejemplo (nunca de una llamada real);
las señales del worker se llaman a mano. Los PNG no se versionan.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from coordinator_live import DEFAULT_MODEL, LiveCoordinator
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


class PreviewCoordinator(LiveCoordinator):
    """El coordinador real sin lanzar el worker ni consultar PipeWire."""

    def read_sources(self) -> SourceChoices:
        return SourceChoices([MONITOR], [MICROPHONE], CaptureSources(MONITOR, MICROPHONE))

    def _launch(self, model: str, devices: dict[str, str]) -> None:
        pass


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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: captura_ui.py <carpeta>")
    for saved in capture_states(Path(sys.argv[1])):
        sys.stdout.write(f"{saved}\n")
