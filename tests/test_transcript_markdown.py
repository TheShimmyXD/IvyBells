from __future__ import annotations

from datetime import datetime

import pytest

from domain.transcription.engine import TranscriptEvent
from domain.transcription.live_view import LatencySummary
from domain.transcription.transcript_markdown import (
    format_header,
    format_latency_footer,
    format_latency_line,
    format_phrase,
    format_resume,
    transcript_stem,
)
from services.service_transcript import TranscriptWriter, free_transcript_path

STARTED = datetime(2026, 10, 17, 18, 5, 30)


def _final(source: str, text: str, start_s: float) -> TranscriptEvent:
    return TranscriptEvent(
        source=source, is_final=True, text=text, start_s=start_s, end_s=start_s + 2
    )


def test_phrase_has_wall_clock_and_label():
    line = format_phrase(_final("tu", " hola a todos ", 95.4), STARTED)
    assert line == "- **18:07:05 Tú:** hola a todos\n"


def test_header_lists_model_and_devices():
    header = format_header(STARTED, "large-v3-turbo int8", {"ellos": "sink.monitor", "tu": "mic"})
    assert header.startswith("# Transcripción 2026-10-17 18:05\n")
    assert "- Ellos: `sink.monitor`" in header
    assert "- Tú: `mic`" in header


def test_stem_and_free_path(tmp_path):
    assert transcript_stem(STARTED) == "2026-10-17_1805"
    (tmp_path / "2026-10-17_1805.md").write_text("", encoding="utf-8")
    assert free_transcript_path(tmp_path, STARTED).name == "2026-10-17_1805_2.md"


def _writer(tmp_path):
    writer = TranscriptWriter(tmp_path / "t")
    assert writer.begin(STARTED, "small int8", {"ellos": "m"})
    return writer


def test_writer_keeps_only_finals(tmp_path):
    writer = _writer(tmp_path)
    writer.add(_final("ellos", "primera", 1.0))
    writer.add(TranscriptEvent(source="ellos", is_final=False, text="prov", start_s=3, end_s=4))
    writer.add(_final("ellos", "segunda", 4.0))
    writer.close()
    text = writer.path.read_text(encoding="utf-8")
    assert writer.phrases == 2
    assert "prov" not in text
    assert text.endswith("- **18:05:31 Ellos:** primera\n- **18:05:34 Ellos:** segunda\n")


def test_latency_line_and_footer():
    ellos = LatencySummary(120, 1.84, 2.43)
    assert format_latency_line("ellos", ellos) == "Ellos: mediana 1,8 s, p90 2,4 s (120 frases)"
    assert format_latency_line("tu", LatencySummary(1, 0.9, 0.9)).endswith("(1 frase)")
    footer = format_latency_footer({"ellos": ellos, "tu": LatencySummary(3, 1.2, 1.6)})
    assert footer == (
        "\n## Latencia\n\n"
        "- Ellos: mediana 1,8 s, p90 2,4 s (120 frases)\n"
        "- Tú: mediana 1,2 s, p90 1,6 s (3 frases)\n"
    )
    assert format_latency_footer({}) == ""


def test_writer_appends_footer_on_close(tmp_path):
    writer = _writer(tmp_path)
    writer.add(_final("ellos", "primera", 1.0))
    writer.close("\n## Latencia\n\n- Ellos: x\n")
    text = writer.path.read_text(encoding="utf-8")
    assert text.endswith("- **18:05:31 Ellos:** primera\n\n## Latencia\n\n- Ellos: x\n")


def test_resume_repeats_only_what_changed():
    devices = {"ellos": "m", "tu": "mic"}
    resumed = datetime(2026, 10, 17, 18, 40, 5)
    same = format_resume(resumed, "turbo int8", devices, "turbo int8", devices)
    assert same == "\n## Reanudada 18:40:05\n\n"
    changed = format_resume(
        resumed, "small int8", {"ellos": "m", "tu": "otro"}, "turbo int8", devices
    )
    assert changed == "\n## Reanudada 18:40:05\n\n- Modelo: small int8\n- Tú: `otro`\n\n"


def test_writer_resumes_in_the_same_file_and_copies_while_open(tmp_path):
    writer = _writer(tmp_path)
    writer.add(_final("ellos", "primera", 1.0))
    writer.end_segment("\n## Latencia\n\n- Ellos: x\n")
    path = writer.path
    assert not writer.begin(datetime(2026, 10, 17, 18, 40, 0), "small int8", {"ellos": "m"})
    writer.add(_final("ellos", "segunda", 2.0))
    copy = tmp_path / "copia.md"
    writer.copy_to(copy)
    text = copy.read_text(encoding="utf-8")
    assert writer.path == path and writer.phrases == 2
    assert text.count("# Transcripción ") == 1
    assert text.endswith("## Reanudada 18:40:00\n\n- **18:40:02 Ellos:** segunda\n")
    writer.close()
    writer.add(_final("ellos", "tarde", 3.0))
    assert writer.phrases == 2


def test_copy_before_any_session_fails(tmp_path):
    with pytest.raises(OSError):
        TranscriptWriter(tmp_path).copy_to(tmp_path / "x.md")
