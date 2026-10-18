from __future__ import annotations

import re

from core.agent_context import MAX_FILE_CHARS
from core.bench_context import CHARS_PER_TOKEN_GUESS, synthetic_context


def test_zero_is_empty():
    assert synthetic_context(0, "a") == ""


def test_size_and_files_follow_the_caps():
    text = synthetic_context(20_000, "a")
    assert abs(len(text) - 20_000 * CHARS_PER_TOKEN_GUESS) < 2_000
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    assert len(sections) == 4
    assert all(len(section) < MAX_FILE_CHARS + 200 for section in sections)


def test_same_seed_same_text_and_seed_goes_first():
    assert synthetic_context(5_000, "a") == synthetic_context(5_000, "a")
    first, second = synthetic_context(5_000, "a"), synthetic_context(5_000, "b")
    lines_a, lines_b = first.splitlines(), second.splitlines()
    assert lines_a[3] != lines_b[3] and "empresa_a" in lines_a[3]
