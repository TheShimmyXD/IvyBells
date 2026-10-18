from __future__ import annotations

import numpy as np
import pytest

from core.engine import TranscriptEvent
from services.service_streaming import SAMPLE_RATE, StreamingEngine
from services.service_vad import VAD_WINDOW_SAMPLES

CHUNK_S = 0.1


def fake_vad(audio: np.ndarray) -> list[float]:
    """Voz = ventana con amplitud media alta."""
    windows = audio.reshape(-1, VAD_WINDOW_SAMPLES)
    return [0.9 if np.abs(window).mean() > 0.1 else 0.0 for window in windows]


def fake_recognizer(audio: np.ndarray) -> str:
    """Una palabra por cada medio segundo con voz: las hipótesis crecen como prefijos."""
    voiced_s = (np.abs(audio) > 0.1).sum() / SAMPLE_RATE
    return " ".join(f"p{index}" for index in range(int(voiced_s * 2)))


def _signal(*parts: tuple[str, float]) -> np.ndarray:
    pieces = [
        np.full(int(seconds * SAMPLE_RATE), 0.5 if kind == "voz" else 0.0)
        for kind, seconds in parts
    ]
    return np.concatenate(pieces).astype(np.float32)


def _feed(engine: StreamingEngine, source: str, audio: np.ndarray) -> None:
    step = int(CHUNK_S * SAMPLE_RATE)
    for start in range(0, len(audio), step):
        engine.feed(source, audio[start : start + step])


@pytest.fixture
def events() -> list[TranscriptEvent]:
    return []


@pytest.fixture
def engine(events: list[TranscriptEvent]) -> StreamingEngine:
    engine = StreamingEngine(events.append, recognizer=fake_recognizer, vad=fake_vad)
    engine.start()
    return engine


def test_partials_grow_and_become_one_final_with_its_times(engine, events):
    _feed(engine, "ellos", _signal(("silencio", 1.0), ("voz", 3.0), ("silencio", 1.0)))

    partials = [event for event in events if not event.is_final]
    finals = [event for event in events if event.is_final]
    assert len(partials) >= 2
    assert all(not event.is_final for event in events[:-1])
    assert [event.stable_words for event in partials] == sorted(
        event.stable_words for event in partials
    )
    assert len(finals) == 1
    final = finals[0]
    assert final.source == "ellos"
    assert final.text == " ".join(f"p{index}" for index in range(6))
    # La frase empieza 0,2 s antes de la voz (audio previo) y cierra tras 0,5 s de silencio.
    assert final.start_s == pytest.approx(0.8, abs=0.05)
    assert final.end_s == pytest.approx(4.5, abs=0.05)


def test_sources_keep_separate_phrases(engine, events):
    audio = _signal(("voz", 1.5), ("silencio", 1.0))
    step = int(CHUNK_S * SAMPLE_RATE)
    for start in range(0, len(audio), step):
        engine.feed("ellos", audio[start : start + step])
        engine.feed("tu", audio[start : start + step])

    finals = [event for event in events if event.is_final]
    assert sorted(event.source for event in finals) == ["ellos", "tu"]
    assert {event.text for event in finals} == {"p0 p1 p2"}


def test_stop_closes_the_open_phrase(engine, events):
    _feed(engine, "tu", _signal(("voz", 2.0)))
    assert not any(event.is_final for event in events)
    engine.stop()
    assert events[-1].is_final
    assert events[-1].text == "p0 p1 p2 p3"


def test_short_noise_is_not_transcribed(engine, events):
    _feed(engine, "ellos", _signal(("silencio", 0.5), ("voz", 0.1), ("silencio", 1.0)))
    assert events == []


def test_partials_are_skipped_while_the_engine_is_behind(events):
    """Cada llamada cuesta 1,5 s y la voz dura 6 s: se atrasa y debe saltar provisionales."""
    now = [0.0]

    def slow_recognizer(audio: np.ndarray) -> str:
        now[0] += 1.5
        return fake_recognizer(audio)

    engine = StreamingEngine(
        events.append, recognizer=slow_recognizer, vad=fake_vad, clock=lambda: now[0]
    )
    audio = _signal(("voz", 6.0), ("silencio", 1.0))
    step = int(CHUNK_S * SAMPLE_RATE)
    for start in range(0, len(audio), step):
        # Como la captura: el bloque se entrega cuando sonó o, si el motor va atrasado, en seguida.
        now[0] = max(now[0], (start + step) / SAMPLE_RATE)
        engine.feed("ellos", audio[start : start + step])

    partials = [event for event in events if not event.is_final]
    finals = [event for event in events if event.is_final]
    # Sin la regla habría un provisional por segundo de voz (6); con ella, la mitad o menos.
    assert 1 <= len(partials) <= 3
    assert len(finals) == 1
    assert finals[0].text == " ".join(f"p{index}" for index in range(12))


def test_shorter_partial_interval_gives_more_partials():
    audio = _signal(("voz", 4.0), ("silencio", 1.0))
    step = int(CHUNK_S * SAMPLE_RATE)
    counts = []
    for interval in (1.0, 0.5):
        received = []
        engine = StreamingEngine(
            received.append, recognizer=fake_recognizer, vad=fake_vad, partial_interval_s=interval
        )
        for start in range(0, len(audio), step):
            engine.feed("ellos", audio[start : start + step])
        counts.append(sum(1 for event in received if not event.is_final))
    assert counts[1] > counts[0] >= 1


def test_end_source_closes_only_that_phrase(engine, events):
    _feed(engine, "ellos", _signal(("voz", 2.0)))
    _feed(engine, "tu", _signal(("voz", 2.0)))
    events.clear()
    engine.end_source("ellos")
    engine.end_source("ellos")
    assert [(event.source, event.is_final) for event in events] == [("ellos", True)]


def test_skip_keeps_phrase_times_on_the_real_clock(engine, events):
    _feed(engine, "ellos", _signal(("voz", 1.0)))
    engine.skip("ellos", 3 * SAMPLE_RATE)
    assert events[-1].is_final
    _feed(engine, "ellos", _signal(("silencio", 1.0), ("voz", 1.0), ("silencio", 1.0)))
    assert events[-1].is_final
    # 1 s de voz + 3 s cerrado + 1 s de silencio, menos el audio previo al disparo.
    assert events[-1].start_s == pytest.approx(4.8, abs=0.1)


def test_skip_counts_the_closed_audio_for_the_lag(events):
    now = [100.0]
    engine = StreamingEngine(
        events.append, recognizer=fake_recognizer, vad=fake_vad, clock=lambda: now[0]
    )
    engine.feed("ellos", np.zeros(SAMPLE_RATE, np.float32))
    now[0] = 103.0
    engine.skip("ellos", 3 * SAMPLE_RATE)
    assert engine.lag_s("ellos") == pytest.approx(0.0)
