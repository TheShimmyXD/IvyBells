from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.agent_context import ContextFile, Omitted, build_context
from core.agent_prompt import Exchange, build_prompt
from core.claude_stream import Finished, Usage, parse_line, parse_usage
from core.context_budget import (
    CLI_OVERHEAD_TOKENS,
    MEASURED_WINDOWS,
    build_budget,
    estimate_tokens,
    format_percent,
    format_tokens,
    path_weights,
    section_chars,
)

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "claude" / "contexto" / "result.json"
BENCH = ROOT / "bench" / "resultados" / "2026-10-17_2040_claude_contexto.json"


def test_usage_from_real_sample():
    usage = parse_usage(json.loads(SAMPLE.read_text(encoding="utf-8")))
    assert usage == Usage(input_tokens=31_265, cached_tokens=31_263, context_window=1_000_000)


def test_finished_carries_the_usage_of_the_stream_sample():
    lines = (SAMPLE.parent.parent / "stream.jsonl").read_text(encoding="utf-8").splitlines()
    finished = [u for u in map(parse_line, lines) if isinstance(u, Finished)]
    assert finished[0].usage is not None and finished[0].usage.input_tokens > 0


def test_usage_missing_or_empty_gives_none():
    assert parse_usage({}) is None
    assert parse_usage({"usage": {"input_tokens": 0}}) is None
    usage = parse_usage({"usage": {"input_tokens": 5}, "modelUsage": {"m": {}}})
    assert usage == Usage(5, 0, None)


def test_window_comes_from_the_model_that_read_more():
    result = {
        "usage": {"input_tokens": 10},
        "modelUsage": {
            "a": {"inputTokens": 1, "contextWindow": 200_000},
            "b": {"inputTokens": 9, "cacheReadInputTokens": 5, "contextWindow": 1_000_000},
        },
    }
    assert parse_usage(result).context_window == 1_000_000


def test_estimate_matches_the_measured_bench_rows():
    rows = json.loads(BENCH.read_text(encoding="utf-8"))["summary"]["rows"]
    assert MEASURED_WINDOWS["haiku"] == json.loads(BENCH.read_text())["summary"]["context_window"]
    for row in rows.values():
        estimate = CLI_OVERHEAD_TOKENS + estimate_tokens(row["chars"])
        assert estimate == pytest.approx(row["input_tokens"], rel=0.01)


def test_parts_follow_the_prompt_builders():
    history = [Exchange("hola", "buenas"), Exchange("precio", "diez")]
    budget = build_budget("reglas", "reglas" + "c" * 234, history, "otra cosa", 1_000_000)
    parts = {part.key: part for part in budget.parts}
    assert parts["rules"].tokens == CLI_OVERHEAD_TOKENS + estimate_tokens(6)
    assert parts["context"].chars == 234 and parts["context"].tokens == 100
    frame = len(build_prompt([], "otra cosa"))
    assert parts["fragment"].chars == frame
    assert parts["history"].chars == len(build_prompt(history, "otra cosa")) - frame
    assert budget.estimated_tokens == sum(part.tokens for part in budget.parts)


def test_history_part_respects_the_prompt_cap():
    history = [Exchange("x" * 500, "y" * 500) for _ in range(30)]
    budget = build_budget("", "", history, "nuevo", None, max_chars=3_000)
    history_part = next(part for part in budget.parts if part.key == "history")
    assert 0 < history_part.chars <= 3_000
    assert history_part.limit_chars == 3_000


def test_no_history_and_no_context_gives_zero_parts():
    budget = build_budget("reglas", "reglas", [], "", None)
    parts = {part.key: part for part in budget.parts}
    assert parts["context"].tokens == 0 and parts["history"].tokens == 0


def test_summary_and_levels():
    budget = build_budget("", "", [], "", None)
    assert "ventana sin medir" in budget.summary()
    assert budget.summary(short=True).endswith("(ventana sin medir)")
    assert budget.fraction is None and budget.level == "ok"
    small = build_budget("", "", [], "", 1_000_000)
    frame = estimate_tokens(len(build_prompt([], "")))
    assert small.summary() == f"~{CLI_OVERHEAD_TOKENS + frame} de 1 M tokens (<1 %)"
    assert small.summary(short=True) == f"~{CLI_OVERHEAD_TOKENS + frame} de 1 M (<1 %)"
    almost = build_budget("", "c" * 2_000_000, [], "", 1_000_000)
    assert almost.level == "warning"
    full = build_budget("", "c" * 2_300_000, [], "", 1_000_000)
    assert full.level == "error"


def test_last_summary_uses_the_real_usage():
    budget = build_budget("", "", [], "", 1_000_000, Usage(31_265, 31_263, 1_000_000), 9.7)
    assert (
        budget.last_summary() == "Último envío: 31,3 k tokens, primer texto 9,7 s, 100 % de caché"
    )
    assert build_budget("", "", [], "", None).last_summary() == ""


@pytest.mark.parametrize(
    ("tokens", "text"),
    [(532, "532"), (1_000, "1 k"), (31_265, "31,3 k"), (121_353, "121 k"), (1_000_000, "1 M")],
)
def test_format_tokens(tokens, text):
    assert format_tokens(tokens) == text


def test_format_percent():
    assert format_percent(None) == "0 %"
    assert format_percent(0.003) == "<1 %"
    assert format_percent(0.5) == "50 %"


def test_section_chars_and_path_weights():
    files = [
        ContextFile("/empresa/servicios.md", "# Servicios\n- Plan básico\n"),
        ContextFile("/empresa/sub/precios.csv", "plan,precio\nbásico,10\n"),
        ContextFile("/manual.txt", "## falso encabezado\n" * 20),
    ]
    text = build_context(files, [Omitted("/empresa/x.xlsx", "Office sin lector")])
    sizes = section_chars(text)
    assert set(sizes) == {file.path for file in files}
    assert sizes["/manual.txt"] > len(files[2].text)
    weights = path_weights(["/empresa", "/manual.txt", "/no/existe"], sizes)
    assert weights["/empresa"] == sizes["/empresa/servicios.md"] + sizes["/empresa/sub/precios.csv"]
    assert weights["/manual.txt"] == sizes["/manual.txt"]
    assert weights["/no/existe"] == 0
    assert path_weights(["/empresa/"], sizes)["/empresa/"] == weights["/empresa"]


def test_section_chars_without_index_is_empty():
    assert section_chars("") == {}
    assert section_chars("texto escrito a mano") == {}
