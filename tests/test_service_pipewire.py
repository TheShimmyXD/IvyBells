from __future__ import annotations

from pathlib import Path

from services.service_pipewire import (
    CaptureSources,
    find_capture_sources,
    parse_info_field,
    parse_short_sources,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pipewire"

ANALOG_MONITOR = "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor"
ANALOG_MIC = "alsa_input.pci-0000_0d_00.4.analog-stereo"
HEADSET_MONITOR = (
    "alsa_output.usb-DODO_Electronics_Inc._Redragon_Gaming_Headset-00.iec958-stereo.monitor"
)
HEADSET_MIC = "alsa_input.usb-DODO_Electronics_Inc._Redragon_Gaming_Headset-00.mono-fallback"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _capture_from_sample(info_name: str, sources_name: str) -> CaptureSources:
    info = _read(info_name)
    return find_capture_sources(
        parse_short_sources(_read(sources_name)),
        default_sink=parse_info_field(info, "Default Sink"),
        default_source=parse_info_field(info, "Default Source"),
    )


def test_parses_real_short_sources_sample():
    sources = parse_short_sources(_read("pactl_list_short_sources.txt"))
    assert [source.name for source in sources] == [ANALOG_MONITOR, ANALOG_MIC]
    assert sources[0].is_monitor
    assert not sources[1].is_monitor
    assert sources[1].state == "SUSPENDED"


def test_reads_default_fields_from_real_info_sample():
    info = _read("pactl_info_headset_usb.txt")
    assert parse_info_field(info, "Default Sink") == HEADSET_MONITOR.removesuffix(".monitor")
    assert parse_info_field(info, "Default Source") == HEADSET_MIC
    assert parse_info_field("Server Name: x\n", "Default Sink") is None


def test_analog_sample_falls_back_to_real_microphone():
    # En esta muestra la entrada predeterminada es la propia .monitor: no sirve de micrófono.
    capture = _capture_from_sample("pactl_info.txt", "pactl_list_short_sources.txt")
    assert capture.monitor is not None and capture.monitor.name == ANALOG_MONITOR
    assert capture.microphone is not None and capture.microphone.name == ANALOG_MIC


def test_usb_headset_sample_follows_the_defaults():
    # Con el headset USB conectado, Meet suena y graba por el headset, no por la placa.
    capture = _capture_from_sample(
        "pactl_info_headset_usb.txt", "pactl_list_short_sources_headset_usb.txt"
    )
    assert capture.monitor is not None and capture.monitor.name == HEADSET_MONITOR
    assert capture.microphone is not None and capture.microphone.name == HEADSET_MIC


def test_malformed_lines_are_skipped():
    text = "x\tfoo\tPipeWire\ts32le\tRUNNING\n\n48\tbad line\n"
    assert parse_short_sources(text) == []


def test_missing_monitor_or_microphone_gives_none():
    sources = parse_short_sources("49\talsa_input.x\tPipeWire\ts32le 2ch\tIDLE\n")
    capture = find_capture_sources(sources)
    assert capture.monitor is None
    assert capture.microphone is not None and capture.microphone.name == "alsa_input.x"
    assert find_capture_sources([]) == CaptureSources(monitor=None, microphone=None)
