from __future__ import annotations

from datetime import datetime

from core.engine import TranscriptEvent
from core.live_view import (
    LatencySummary,
    LatencyTracker,
    LiveTranscript,
    format_latency,
    short_device_name,
)


def _event(source, text, final, start_s=1.0, end_s=2.0):
    return TranscriptEvent(source, final, text, start_s, end_s)


def test_partial_is_replaced_and_cleared_by_final():
    transcript = LiveTranscript()
    transcript.reset(datetime(2026, 10, 17, 18, 5, 0))
    transcript.apply(_event("tu", "hola", False, start_s=31.0))
    transcript.apply(_event("tu", "hola a todos", False, start_s=31.0))
    assert transcript.partial("tu").text == "hola a todos"
    assert transcript.partial("tu").clock == "18:05:31"
    transcript.apply(_event("tu", " Hola a todos. ", True, start_s=31.0))
    assert transcript.partial("tu") is None
    assert [line.text for line in transcript.finals("tu")] == ["Hola a todos."]
    assert transcript.finals("ellos") == []


def test_empty_final_is_dropped_and_reset_clears():
    transcript = LiveTranscript()
    transcript.reset(datetime(2026, 10, 17))
    transcript.apply(_event("ellos", "algo", False))
    transcript.apply(_event("ellos", "  ", True))
    assert transcript.finals("ellos") == []
    assert transcript.partial("ellos") is None
    transcript.apply(_event("ellos", "frase", True))
    transcript.reset(datetime(2026, 10, 17))
    assert transcript.finals("ellos") == []


def test_latency_from_first_block_like_bench():
    tracker = LatencyTracker(sample_rate=16_000)
    assert tracker.add_final(1.0, now=5.0) is None
    tracker.mark_audio(1_600, now=100.1)  # el bloque de 0,1 s empezo a sonar en 100,0
    tracker.mark_audio(1_600, now=100.2)  # solo el primero cuenta
    assert abs(tracker.add_final(end_s=2.0, now=103.5) - 1.5) < 1e-9
    assert abs(tracker.add_final(end_s=5.0, now=107.5) - 2.5) < 1e-9
    assert abs(tracker.last - 2.5) < 1e-9
    assert abs(tracker.median - 2.0) < 1e-9


def test_latency_summary_per_source_in_sources_order():
    tracker = LatencyTracker(sample_rate=16_000)
    assert tracker.summary() == {}
    tracker.mark_audio(1_600, now=100.1)  # origen en 100,0
    for end_s, now in ((1.0, 102.0), (2.0, 104.0), (3.0, 106.0)):  # 1, 2 y 3 s
        tracker.add_final(end_s, now, "tu")
    tracker.add_final(5.0, 106.5, "ellos")  # 1,5 s
    summary = tracker.summary()
    assert list(summary) == ["ellos", "tu"]
    assert summary["tu"] == LatencySummary(3, 2.0, 3.0)
    assert summary["ellos"] == LatencySummary(1, 1.5, 1.5)


def test_short_device_names_from_fixtures():
    assert (
        short_device_name("alsa_output.pci-0000_0d_00.4.analog-stereo.monitor")
        == "analog-stereo.monitor"
    )
    assert short_device_name("alsa_input.pci-0000_0d_00.4.analog-stereo") == "analog-stereo"
    assert short_device_name("bluez_input.algo") == "bluez_input.algo"


def test_format_latency():
    assert format_latency(None, None) == "Latencia -"
    assert format_latency(1.62, 1.78) == "Latencia 1,6 s, mediana 1,8 s"
