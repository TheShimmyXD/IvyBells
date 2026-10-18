from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from core.claude_model import ClaudeModelConfig
from services.service_claude import ClaudeCancelled, ClaudeCli, ClaudeError, ScriptedClaude

FIXTURE = Path(__file__).parent / "fixtures" / "claude" / "stream.jsonl"

# CLI falsa: lee el prompt, guarda su pid y se comporta según el modo.
_FAKE_CLI = """#!{python}
import json, os, sys, time
mode, fixture, pidfile, promptfile = {mode!r}, {fixture!r}, {pidfile!r}, {promptfile!r}
open(promptfile, "w", encoding="utf-8").write(sys.stdin.read())
open(pidfile, "w").write(str(os.getpid()))
if mode == "ok":
    for line in open(fixture, encoding="utf-8"):
        print(line, end="", flush=True)
elif mode == "error_result":
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": True,
                      "result": "Límite de uso alcanzado"}}), flush=True)
elif mode == "no_result":
    print("Error: sesión no iniciada", file=sys.stderr)
    sys.exit(3)
elif mode == "hang":
    delta = {{"type": "stream_event", "event": {{"type": "content_block_delta",
             "delta": {{"type": "text_delta", "text": "Hola"}}}}}}
    print(json.dumps(delta), flush=True)
    time.sleep(30)
"""


def _cli(tmp_path, mode, timeout_s=10):
    script = tmp_path / f"fake_claude_{mode}"
    script.write_text(
        _FAKE_CLI.format(
            python=sys.executable,
            mode=mode,
            fixture=str(FIXTURE),
            pidfile=str(tmp_path / "pid"),
            promptfile=str(tmp_path / "prompt"),
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    config = ClaudeModelConfig(executable=str(script), timeout_s=timeout_s)
    return ClaudeCli(config, "perfil", tmp_path / "neutral")


def _process_gone(tmp_path) -> bool:
    pid = int((tmp_path / "pid").read_text())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def test_stream_arrives_in_pieces_and_matches_the_result(tmp_path):
    chunks = []
    result = _cli(tmp_path, "ok").ask("hola", chunks.append, threading.Event())
    assert len(chunks) > 1
    assert "".join(chunks) == result.text
    assert (tmp_path / "prompt").read_text(encoding="utf-8") == "hola"
    assert (tmp_path / "neutral").is_dir()


def test_error_result_raises_with_the_cli_message(tmp_path):
    with pytest.raises(ClaudeError, match="Límite de uso"):
        _cli(tmp_path, "error_result").ask("hola", lambda _: None, threading.Event())


def test_exit_without_result_reports_stderr(tmp_path):
    with pytest.raises(ClaudeError, match="sesión no iniciada"):
        _cli(tmp_path, "no_result").ask("hola", lambda _: None, threading.Event())


def test_timeout_kills_the_process(tmp_path):
    start = time.monotonic()
    with pytest.raises(ClaudeError, match="no respondió en 1 s"):
        _cli(tmp_path, "hang", timeout_s=1).ask("hola", lambda _: None, threading.Event())
    assert time.monotonic() - start < 6
    assert _process_gone(tmp_path)


def test_cancel_kills_the_process(tmp_path):
    cancel = threading.Event()
    with pytest.raises(ClaudeCancelled):
        _cli(tmp_path, "hang").ask("hola", lambda _: cancel.set(), cancel)
    assert _process_gone(tmp_path)


def test_missing_executable(tmp_path):
    config = ClaudeModelConfig(executable=str(tmp_path / "no_existe"))
    with pytest.raises(ClaudeError, match="No se pudo lanzar"):
        ClaudeCli(config, "perfil", tmp_path).ask("hola", lambda _: None, threading.Event())


def test_scripted_service():
    chunks = []
    service = ScriptedClaude(["Buenas ", "tardes."])
    assert service.ask("p", chunks.append, threading.Event()).text == "Buenas tardes."
    assert chunks == ["Buenas ", "tardes."]
    assert service.prompts == ["p"]
    with pytest.raises(ClaudeError, match="caído"):
        ScriptedClaude(["a"], error="caído").ask("p", lambda _: None, threading.Event())
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ClaudeCancelled):
        ScriptedClaude(["a"]).ask("p", lambda _: None, cancel)
