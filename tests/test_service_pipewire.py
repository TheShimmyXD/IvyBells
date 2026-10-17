from __future__ import annotations

from pathlib import Path

from services.service_pipewire import (
    find_capture_sources,
    parse_default_source,
    parse_short_sources,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pipewire"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_real_short_sources_sample():
    sources = parse_short_sources(_read("pactl_list_short_sources.txt"))
    assert [source.name for source in sources] == [
        "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor",
        "alsa_input.pci-0000_0d_00.4.analog-stereo",
    ]
    assert sources[0].is_monitor
    assert not sources[1].is_monitor
    assert sources[1].state == "SUSPENDED"


def test_reads_default_source_from_real_info_sample():
    default = parse_default_source(_read("pactl_info.txt"))
    assert default == "alsa_output.pci-0000_0d_00.4.analog-stereo.monitor"


def test_picks_monitor_and_microphone_from_real_sample():
    sources = parse_short_sources(_read("pactl_list_short_sources.txt"))
    default = parse_default_source(_read("pactl_info.txt"))
    capture = find_capture_sources(sources, default)
    assert capture.monitor is not None
    assert capture.monitor.name == default
    assert capture.microphone is not None
    assert capture.microphone.name == "alsa_input.pci-0000_0d_00.4.analog-stereo"


def test_malformed_lines_are_skipped():
    text = "x\tfoo\tPipeWire\ts32le\tRUNNING\n\n48\tbad line\n"
    assert parse_short_sources(text) == []


def test_missing_monitor_or_microphone_gives_none():
    sources = parse_short_sources("49\talsa_input.x\tPipeWire\ts32le 2ch\tIDLE\n")
    capture = find_capture_sources(sources)
    assert capture.monitor is None
    assert capture.microphone is not None
    assert parse_default_source("Server Name: x\n") is None
