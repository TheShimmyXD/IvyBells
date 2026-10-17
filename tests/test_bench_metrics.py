from __future__ import annotations

import pytest

from core.bench_metrics import (
    format_table,
    median_s,
    peak_over_baseline,
    pick_window_start,
    real_time_factor,
    text_health,
)


def test_real_time_factor_divides_compute_by_audio():
    assert real_time_factor(18.0, 180.0) == pytest.approx(0.1)


def test_real_time_factor_rejects_empty_audio():
    with pytest.raises(ValueError):
        real_time_factor(1.0, 0.0)


def test_peak_over_baseline_subtracts_desktop_usage():
    assert peak_over_baseline([360, 1800, 2400, 900], 358) == 2042
    assert peak_over_baseline([], 358) == 0
    assert peak_over_baseline([300], 358) == 0


def test_median_s_handles_empty_and_odd_lists():
    assert median_s([]) == 0.0
    assert median_s([0.9, 0.3, 0.5]) == 0.5


def test_text_health_accepts_spanish_text():
    health = text_health("Hola, ¿me escuchas bien? Sí, perfecto.")
    assert health.words == 6
    assert not health.looks_broken


def test_text_health_flags_empty_and_symbol_garbage():
    assert text_health("").looks_broken
    assert text_health("   ").looks_broken
    assert text_health("!!!! ???? !!!! ....").looks_broken


def test_pick_window_start_uses_first_segment_that_fits():
    assert pick_window_start([2.0, 50.0], audio_s=180.0, window_s=5.0) == 2.0
    assert pick_window_start([178.0], audio_s=180.0, window_s=5.0) == pytest.approx(87.5)
    assert pick_window_start([], audio_s=4.0, window_s=5.0) == 0.0


def test_format_table_shows_measured_and_failed_rows():
    rows = [
        {
            "model": "small",
            "compute_type": "int8",
            "load_s": 1.23,
            "vram_peak_mib": 812,
            "window": {"median_s": 0.41},
            "tracks": {
                "sonido": {"rtf": 0.05, "looks_broken": False},
                "microfono": {"rtf": 0.04, "looks_broken": False},
            },
        },
        {"model": "large-v3", "compute_type": "float16", "error": "CUDA out of memory"},
    ]
    table = format_table(rows)
    assert "| small | int8 | 1.2 | 0.050 | 0.040 | 0.41 s | 812 | ok |" in table
    assert "falla: CUDA out of memory" in table
