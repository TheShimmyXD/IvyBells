from __future__ import annotations

from core.phrase_segmenter import PhraseEvent, PhraseEventKind, PhraseSegmenter

START = PhraseEventKind.START
END = PhraseEventKind.END


def _run(segmenter: PhraseSegmenter, probs: list[float]) -> list[PhraseEvent]:
    events: list[PhraseEvent] = []
    for prob in probs:
        events.extend(segmenter.push(prob))
    return events


def test_phrase_starts_on_speech_and_ends_after_enough_silence():
    segmenter = PhraseSegmenter(min_silence_windows=3, max_phrase_windows=100)
    events = _run(segmenter, [0.1, 0.9, 0.8, 0.1, 0.1, 0.1, 0.1])
    assert events == [PhraseEvent(START, 1), PhraseEvent(END, 6)]
    assert not segmenter.in_speech


def test_short_pause_does_not_cut_the_phrase():
    segmenter = PhraseSegmenter(min_silence_windows=3, max_phrase_windows=100)
    events = _run(segmenter, [0.9, 0.1, 0.1, 0.9, 0.9])
    assert events == [PhraseEvent(START, 0)]
    assert segmenter.in_speech


def test_hysteresis_keeps_speech_between_thresholds():
    segmenter = PhraseSegmenter(min_silence_windows=2, max_phrase_windows=100)
    # 0.4 no abre una frase, pero tampoco cuenta como silencio dentro de una.
    assert _run(segmenter, [0.4, 0.4]) == []
    events = _run(segmenter, [0.6, 0.4, 0.4, 0.4, 0.2, 0.2])
    assert events == [PhraseEvent(START, 2), PhraseEvent(END, 8)]


def test_long_phrase_is_forced_to_end_and_continues():
    segmenter = PhraseSegmenter(min_silence_windows=3, max_phrase_windows=4)
    events = _run(segmenter, [0.9] * 6)
    assert events == [
        PhraseEvent(START, 0),
        PhraseEvent(END, 4, forced=True),
        PhraseEvent(START, 4),
    ]


def test_skip_ends_speech_and_keeps_window_numbers():
    segmenter = PhraseSegmenter(min_silence_windows=2, max_phrase_windows=100)
    assert _run(segmenter, [0.9]) == [PhraseEvent(START, 0)]
    segmenter.skip(10)
    assert not segmenter.in_speech
    assert _run(segmenter, [0.9]) == [PhraseEvent(START, 11)]
