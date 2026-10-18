from __future__ import annotations

import json
from pathlib import Path

from core.claude_stream import Finished, TextDelta, parse_line

FIXTURE = Path(__file__).parent / "fixtures" / "claude" / "stream.jsonl"


def test_real_sample_deltas_rebuild_the_final_text():
    updates = [parse_line(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]
    deltas = [u.text for u in updates if isinstance(u, TextDelta)]
    finished = [u for u in updates if isinstance(u, Finished)]
    assert len(deltas) > 1
    assert len(finished) == 1
    assert not finished[0].is_error
    assert "".join(deltas) == finished[0].text
    assert finished[0].duration_ms and finished[0].ttft_ms


def test_thinking_and_other_events_are_ignored():
    thinking = {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta"}},
    }
    assert parse_line(json.dumps(thinking)) is None
    assert parse_line(json.dumps({"type": "system", "subtype": "init"})) is None
    assert parse_line("no es json") is None
    assert parse_line("[1, 2]") is None
    assert parse_line("") is None


def test_error_result():
    line = json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "x"})
    assert parse_line(line) == Finished("x", True)
    line = json.dumps({"type": "result", "subtype": "error_max_turns", "errors": ["a", "b"]})
    assert parse_line(line) == Finished("a; b", True)
