from __future__ import annotations

from datetime import datetime

from core.engine import TranscriptEvent
from core.transcript_markdown import format_header, format_phrase, transcript_stem
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


def test_writer_keeps_only_finals(tmp_path):
    writer = TranscriptWriter(tmp_path / "t", STARTED, "small int8", {"ellos": "m"})
    writer.add(_final("ellos", "primera", 1.0))
    writer.add(TranscriptEvent(source="ellos", is_final=False, text="prov", start_s=3, end_s=4))
    writer.add(_final("ellos", "segunda", 4.0))
    writer.close()
    text = writer.path.read_text(encoding="utf-8")
    assert writer.phrases == 2
    assert "prov" not in text
    assert text.endswith("- **18:05:31 Ellos:** primera\n- **18:05:34 Ellos:** segunda\n")
