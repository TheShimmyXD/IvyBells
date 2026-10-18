from __future__ import annotations

import json

from bench.bench_claude import summarize_context, usage_of
from paths import ROOT


def test_usage_of_sample_result():
    result = json.loads((ROOT / "tests/fixtures/claude/result.json").read_text(encoding="utf-8"))
    usage = usage_of(result)
    assert usage["input_tokens"] == 2 + 0 + 698
    assert usage["cache_read_tokens"] == 698 and usage["output_tokens"] == 237
    assert usage["context_window"] == 1_000_000


def _run(size, phase, tokens, chars, first):
    return {"context_tokens": size, "phase": phase, "ok": True, "first_text_s": first,
            "total_s": first + 1, "input_tokens": tokens, "cache_read_tokens": 0,
            "chars": chars, "context_window": 1_000_000}  # fmt: skip


def test_summary_chars_per_token_against_empty_context():
    runs = [
        _run(0, "frio", 1_000, 3_000, 2.0),
        _run(0, "cache", 1_000, 3_000, 1.5),
        _run(20_000, "frio", 21_000, 73_000, 3.0),
        _run(20_000, "cache", 21_000, 73_000, 2.0),
    ]
    summary = summarize_context(runs)
    assert summary["chars_per_token"] == {"20000": 3.5}
    assert summary["rows"]["20000_cache"]["first_text_median_s"] == 2.0
    assert summary["context_window"] == 1_000_000
