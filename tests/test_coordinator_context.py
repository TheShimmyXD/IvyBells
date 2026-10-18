from __future__ import annotations

import threading
import time

import pytest

from coordinator_context import AgentContext
from services.service_context import write_context


def _wait(qapp, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition():
        qapp.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("se agotó la espera")
        time.sleep(0.01)


def _reload(qapp, context):
    context.reload()
    _wait(qapp, lambda: not context.is_busy())


@pytest.fixture
def context(qapp, tmp_path):
    folder = tmp_path / "empresa"
    folder.mkdir()
    (folder / "servicios.md").write_text("Plan básico", encoding="utf-8")
    (folder / "catalogo.pdf").write_bytes(b"%PDF")
    saved = []
    coordinator = AgentContext([], saved.append, target=tmp_path / "contexto.md")
    coordinator.saved = saved
    coordinator.folder = folder
    return coordinator


def test_paths_are_cleaned_and_remembered(context):
    context.set_paths(["  /a", "", "/a", "/b"])
    assert context.paths == ["/a", "/b"]
    context.add(["/b", "/c"])
    assert context.saved == [["/a", "/b"], ["/a", "/b", "/c"]]


def test_reload_reports_files_and_omitted(qapp, context):
    notices = []
    context.reloaded.connect(notices.append)
    context.add([str(context.folder)])
    _reload(qapp, context)
    assert [n["level"] for n in notices] == ["busy", "warning"]
    assert "1 archivos" in notices[-1]["text"] and "catalogo.pdf" in notices[-1]["text"]
    assert "Plan básico" in context.text()
    _reload(qapp, context)
    assert notices[-1]["text"].endswith("(sin cambios)")


def test_no_paths(qapp, context):
    notices = []
    context.reloaded.connect(notices.append)
    _reload(qapp, context)
    assert notices[-1]["level"] == "info"
    assert context.text() == ""


def test_reload_does_not_block_and_queues_one_more(qapp, tmp_path):
    release = threading.Event()
    calls = []

    def slow_writer(paths, target):
        calls.append(list(paths))
        release.wait(5)
        return write_context(paths, target)

    context = AgentContext(["/a"], target=tmp_path / "contexto.md", writer=slow_writer)
    started = time.monotonic()
    context.reload()
    assert time.monotonic() - started < 0.5 and context.is_busy()
    context.set_paths(["/b"])
    context.reload()
    context.reload()
    release.set()
    _wait(qapp, lambda: len(calls) == 2 and not context.is_busy())
    assert calls == [["/a"], ["/b"]]


def test_writer_error_is_reported(qapp, tmp_path):
    def broken(paths, target):
        raise OSError("disco lleno")

    context = AgentContext(["/a"], target=tmp_path / "contexto.md", writer=broken)
    notices = []
    context.reloaded.connect(notices.append)
    _reload(qapp, context)
    assert notices[-1] == {"text": "No se pudo rehacer contexto.md: disco lleno", "level": "error"}


def test_editor_buttons(qapp, context, monkeypatch):
    import ui.context_editor as module

    monkeypatch.setattr(module, "pick_folder", lambda _parent: str(context.folder))
    editor = module.ContextEditor(context)
    assert not editor.open_button.isEnabled()
    editor.add_folder_button.click()
    assert editor.paths_edit.toPlainText() == str(context.folder)
    editor.reload_button.click()
    assert not editor.reload_button.isEnabled()
    _wait(qapp, lambda: not context.is_busy())
    assert editor.reload_button.isEnabled() and editor.open_button.isEnabled()
    editor.remove_button.click()
    assert context.paths == []
