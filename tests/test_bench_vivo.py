from __future__ import annotations

from bench.bench_vivo import _Recorder, _summarize
from core.engine import TranscriptEvent


def _event(source: str, end_s: float, is_final: bool = True) -> TranscriptEvent:
    return TranscriptEvent(
        source=source, text="hola", start_s=end_s - 1.0, end_s=end_s, is_final=is_final
    )


def test_summary_splits_final_latency_by_source():
    recorder = _Recorder()
    recorder.received = [
        (2.0, _event("ellos", 1.0)),
        (3.5, _event("tu", 3.0)),
        (6.0, _event("ellos", 5.0, is_final=False)),
        (8.0, _event("ellos", 5.0)),
    ]
    summary = _summarize(recorder)
    assert summary["frases_finales"] == 3
    assert summary["por_fuente"]["ellos"]["frases_finales"] == 2
    assert summary["por_fuente"]["ellos"]["max"] == 3.0
    assert summary["por_fuente"]["tu"]["mediana"] == 0.5
