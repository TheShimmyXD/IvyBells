from __future__ import annotations

import pytest

from coordinator_context import AgentContext


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


def test_reload_reports_files_and_omitted(context):
    notices = []
    context.reloaded.connect(notices.append)
    context.add([str(context.folder)])
    context.reload()
    assert notices[-1]["level"] == "warning"
    assert "1 archivos" in notices[-1]["text"] and "catalogo.pdf" in notices[-1]["text"]
    assert "Plan básico" in context.text()
    context.reload()
    assert notices[-1]["text"].endswith("(sin cambios)")


def test_no_paths(context):
    notices = []
    context.reloaded.connect(notices.append)
    context.reload()
    assert notices[-1]["level"] == "info"
    assert context.text() == ""


def test_editor_buttons(context, monkeypatch):
    import ui.context_editor as module

    monkeypatch.setattr(module, "pick_folder", lambda _parent: str(context.folder))
    editor = module.ContextEditor(context)
    assert not editor.open_button.isEnabled()
    editor.add_folder_button.click()
    assert editor.paths_edit.toPlainText() == str(context.folder)
    editor.reload_button.click()
    assert editor.open_button.isEnabled()
    editor.remove_button.click()
    assert context.paths == []
