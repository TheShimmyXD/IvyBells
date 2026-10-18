from __future__ import annotations

import json

import pytest

from captura_ui import PreviewCoordinator
from config import AppConfig, load_app_config, save_app_config
from core.live_view import resolve_device
from services.service_pipewire import AudioSource, CaptureSources, SourceChoices

SPEAKERS = AudioSource(48, "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor", "", "", "")
HEADSET = AudioSource(60, "alsa_output.usb-Headset-00.analog-stereo.monitor", "", "", "")
MIC = AudioSource(49, "alsa_input.pci-0000_0d_00.4.analog-stereo", "", "", "")
HEADSET_MIC = AudioSource(61, "alsa_input.usb-Headset-00.mono-fallback", "", "", "")


class _PluggableCoordinator(PreviewCoordinator):
    """Escucha de prueba cuyas fuentes cambian como al conectar unos audífonos USB."""

    def __init__(self) -> None:
        super().__init__()
        self.plug(False)

    def plug(self, headset: bool, default_headset: bool = True) -> None:
        monitors = [SPEAKERS, HEADSET] if headset else [SPEAKERS]
        inputs = [MIC, HEADSET_MIC] if headset else [MIC]
        on_headset = headset and default_headset
        self.choices = SourceChoices(
            monitors,
            inputs,
            CaptureSources(HEADSET if on_headset else SPEAKERS, HEADSET_MIC if on_headset else MIC),
        )

    def read_sources(self) -> SourceChoices:
        return self.choices


@pytest.fixture
def make_page(qapp):
    """Páginas sueltas que se borran al terminar (antes de que se cierre la QApplication)."""
    from PySide6.QtCore import QCoreApplication, QEvent

    from ui.live_page import LivePage

    pages = []

    def build(preferred=None):
        coordinator = _PluggableCoordinator()
        page = LivePage(coordinator, preferred)
        chosen = []
        page.devices_chosen.connect(chosen.append)
        pages.append(page)
        return coordinator, page, chosen

    yield build
    for page in pages:
        page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _choose(page, source, name):
    box = page.source_boxes[source]
    index = box.findData(name)
    box.setCurrentIndex(index)
    box.activated.emit(index)


def test_resolve_device_rule():
    names = ["a", "b"]
    assert resolve_device(names, "b", "a") == "b"
    assert resolve_device(names, "", "a") == "a"
    assert resolve_device(names, "gone", "a") == "a"
    assert resolve_device(names, "gone", "gone too") == "a"
    assert resolve_device([], "a", "a") is None


def test_default_follows_the_system_when_headset_is_plugged(make_page):
    coordinator, page, chosen = make_page()
    assert page.selected_devices() == {"ellos": SPEAKERS.name, "tu": MIC.name}
    assert page.source_boxes["ellos"].currentText().startswith("Predeterminada (")
    coordinator.plug(True)
    page.refresh_sources()
    assert page.selected_devices() == {"ellos": HEADSET.name, "tu": HEADSET_MIC.name}
    assert chosen == []  # nadie eligió nada: no se guarda


def test_chosen_device_is_kept_while_unplugged_and_comes_back(make_page):
    coordinator, page, chosen = make_page()
    coordinator.plug(True, default_headset=False)
    page.refresh_sources()
    _choose(page, "ellos", HEADSET.name)
    assert chosen == [{"ellos": HEADSET.name}]
    coordinator.plug(False)
    page.refresh_sources()
    assert page.selected_devices()["ellos"] == SPEAKERS.name
    assert "no está conectada" in page.source_boxes["ellos"].toolTip()
    coordinator.plug(True, default_headset=False)
    page.refresh_sources()
    assert page.selected_devices()["ellos"] == HEADSET.name
    assert len(chosen) == 1  # desconectar y reconectar no cambia la elección guardada


def test_saved_choice_applies_on_start_and_default_can_be_chosen_again(make_page):
    coordinator, page, chosen = make_page({"tu": MIC.name})
    coordinator.plug(True)
    page.refresh_sources()
    assert page.selected_devices() == {"ellos": HEADSET.name, "tu": MIC.name}
    _choose(page, "tu", "")
    assert chosen == [{}]
    assert page.selected_devices()["tu"] == HEADSET_MIC.name


def test_start_uses_the_sources_read_just_before(make_page):
    coordinator, page, _chosen = make_page()
    coordinator.plug(True)
    page.toggle_run()  # sin esperar al temporizador
    assert coordinator.logic.can_stop


def test_new_preferences_round_trip_and_bad_values_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    original = AppConfig(
        live_model="small", devices={"ellos": HEADSET.name}, speaker="tu", module="agent"
    )
    assert save_app_config(original, path)
    assert load_app_config(path) == original
    path.write_text(
        json.dumps(
            {"devices": {"ellos": 3, "nadie": "x", "tu": " "}, "speaker": "otro", "module": "?"}
        ),
        encoding="utf-8",
    )
    config = load_app_config(path)
    assert config.devices == {}
    assert config.speaker == "ellos"
    assert config.module == "live"
    assert config.live_model == "large-v3-turbo"
