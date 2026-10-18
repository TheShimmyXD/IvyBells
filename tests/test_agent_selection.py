from __future__ import annotations

from core.agent_selection import WordPos, select_phrases, select_range, word_at
from core.live_view import Line

LINES = [
    Line("10:00:01", "buenas tardes con quién hablo"),
    Line("10:00:05", "quería saber el precio del plan"),
    Line("10:00:09", "para una empresa pequeña gracias"),
]


def test_range_inside_one_phrase():
    selection = select_range(LINES, WordPos(1, 1), WordPos(1, 3))
    assert selection.text() == "[10:00:05] saber el precio"


def test_range_across_phrases_takes_everything_between():
    selection = select_range(LINES, WordPos(0, 3), WordPos(2, 3))
    assert [line.text for line in selection.lines] == [
        "quién hablo",
        "quería saber el precio del plan",
        "para una empresa pequeña",
    ]
    assert selection.text().splitlines()[0] == "[10:00:01] quién hablo"


def test_end_before_start_is_swapped():
    forward = select_range(LINES, WordPos(0, 1), WordPos(1, 1))
    backward = select_range(LINES, WordPos(1, 1), WordPos(0, 1))
    assert forward == backward
    assert backward.start == WordPos(0, 1)


def test_same_phrase_reversed_words_is_swapped():
    selection = select_range(LINES, WordPos(2, 3), WordPos(2, 1))
    assert selection.text() == "[10:00:09] una empresa pequeña"


def test_word_beyond_phrase_is_clamped():
    selection = select_range(LINES, WordPos(0, 99), WordPos(1, 99))
    assert [line.text for line in selection.lines] == [
        "hablo",
        "quería saber el precio del plan",
    ]


def test_out_of_range_phrase_or_empty_list_gives_none():
    assert select_range(LINES, WordPos(0, 0), WordPos(5, 0)) is None
    assert select_range([], WordPos(0, 0), WordPos(0, 0)) is None


def test_single_word():
    assert select_range(LINES, WordPos(1, 3), WordPos(1, 3)).lines[0].text == "precio"


def test_word_at_offsets():
    text = "hola  buenas tardes"
    assert word_at(text, 0) == 0
    assert word_at(text, 3) == 0
    assert word_at(text, 5) == 0  # en el espacio: la palabra anterior
    assert word_at(text, 6) == 1
    assert word_at(text, 18) == 2
    assert word_at(text, 500) == 2
    assert word_at("", 0) == 0


def test_line_without_clock_has_no_brackets():
    selection = select_range([Line("", "hola")], WordPos(0, 0), WordPos(0, 0))
    assert selection.text() == "hola"


def test_whole_phrase_from_two_clicks_on_it():
    selection = select_phrases(LINES, WordPos(1, 2), WordPos(1, 3))
    assert selection.text() == "[10:00:05] quería saber el precio del plan"
    assert (selection.start, selection.end) == (WordPos(1, 0), WordPos(1, 5))


def test_whole_phrases_across_several():
    selection = select_phrases(LINES, WordPos(0, 3), WordPos(2, 1))
    assert [line.text for line in selection.lines] == [line.text for line in LINES]


def test_whole_phrases_reversed_clicks():
    forward = select_phrases(LINES, WordPos(1, 4), WordPos(2, 0))
    backward = select_phrases(LINES, WordPos(2, 0), WordPos(1, 4))
    assert forward == backward
    assert backward.lines[0].text == "quería saber el precio del plan"
    assert backward.end == WordPos(2, 4)


def test_whole_phrases_out_of_range_gives_none():
    assert select_phrases(LINES, WordPos(0, 0), WordPos(3, 0)) is None
    assert select_phrases([], WordPos(0, 0), WordPos(0, 0)) is None
