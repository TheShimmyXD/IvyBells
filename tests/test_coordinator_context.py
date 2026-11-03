from __future__ import annotations

import threading
import time

import pytest

from coordinator_context import AgentContext
from services.service_context import write_context
from services.service_contexts import ContextStore


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
    store = ContextStore(tmp_path / "contextos")
    folder = store.path(store.create("empresa"))
    (folder / "servicios.md").write_text("Plan básico", encoding="utf-8")
    (folder / "catalogo.pdf").write_bytes(b"%PDF")
    saved = []
    coordinator = AgentContext("", saved.append, target=tmp_path / "contexto.md", store=store)
    coordinator.saved = saved
    return coordinator


def test_set_active_remembers_and_reloads(qapp, context):
    notices = []
    context.reloaded.connect(notices.append)
    context.set_active("no_existe")
    assert context.active == "" and context.paths == [] and context.saved == []
    context.set_active("empresa")
    _wait(qapp, lambda: not context.is_busy())
    assert context.saved == ["empresa"]
    assert context.paths == [str(context.store.path("empresa"))]
    assert [n["level"] for n in notices] == ["busy", "warning"]
    assert "1 archivos" in notices[-1]["text"] and "catalogo.pdf" in notices[-1]["text"]
    assert "Plan básico" in context.text()
    weights = context.weights()
    assert weights[str(context.folder / "servicios.md")] > 0
    assert weights[str(context.folder / "catalogo.pdf")] == 0
    _reload(qapp, context)
    assert notices[-1]["text"].endswith("(sin cambios)")
    context.set_active("")
    _wait(qapp, lambda: not context.is_busy())
    assert context.saved == ["empresa", ""] and context.text() == ""


def test_remembered_context_that_no_longer_exists(tmp_path):
    context = AgentContext("borrado", target=tmp_path / "contexto.md", store=ContextStore(tmp_path))
    assert context.active == "" and context.folder is None and context.weights() == {}


def test_create_and_rename(qapp, context):
    changes = []
    context.contexts_changed.connect(lambda: changes.append("lista"))
    assert context.create("entrevista") == "entrevista"
    _wait(qapp, lambda: not context.is_busy())
    assert context.active == "entrevista" and context.saved == ["entrevista"]
    assert context.rename("entrevista", "logistica") == "logistica"
    _wait(qapp, lambda: not context.is_busy())
    assert context.active == "logistica" and context.saved[-1] == "logistica"
    assert context.rename("empresa", "otra") == "otra" and context.active == "logistica"
    assert changes == ["lista"] * 3


def test_errors_go_to_the_status(context):
    notices = []
    context.reloaded.connect(notices.append)
    assert context.create("empresa") == ""
    assert context.rename("empresa", "///") == ""
    assert [n["level"] for n in notices] == ["error", "error"]


def test_no_context(qapp, context):
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

    store = ContextStore(tmp_path / "contextos")
    store.create("a")
    store.create("b")
    context = AgentContext("a", target=tmp_path / "contexto.md", writer=slow_writer, store=store)
    started = time.monotonic()
    context.reload()
    assert time.monotonic() - started < 0.5 and context.is_busy()
    context.set_active("b")
    context.reload()
    release.set()
    _wait(qapp, lambda: len(calls) == 2 and not context.is_busy())
    assert calls == [[str(store.path("a"))], [str(store.path("b"))]]


def test_writer_error_is_reported(qapp, tmp_path):
    def broken(paths, target):
        raise OSError("disco lleno")

    context = AgentContext(target=tmp_path / "contexto.md", writer=broken)
    notices = []
    context.reloaded.connect(notices.append)
    _reload(qapp, context)
    assert notices[-1] == {"text": "No se pudo rehacer contexto.md: disco lleno", "level": "error"}


def test_editor(qapp, context, monkeypatch):
    import ui.context_editor as module

    opened = []
    monkeypatch.setattr(module, "open_folder", opened.append)
    monkeypatch.setattr(module, "ask_name", lambda _parent, _title, _current: "logistica")
    editor = module.ContextEditor(context)
    combo = editor.combo
    assert [combo.itemText(i) for i in range(combo.count())] == [module.NO_CONTEXT, "empresa"]
    assert not editor.open_button.isEnabled() and not editor.rename_button.isEnabled()
    combo.setCurrentIndex(1)
    combo.activated.emit(1)
    assert not editor.reload_button.isEnabled()
    _wait(qapp, lambda: not context.is_busy())
    assert context.active == "empresa" and editor.reload_button.isEnabled()
    assert editor.open_button.isEnabled() and editor.rename_button.isEnabled()
    assert "servicios.md" in editor.weights_label.text()
    editor.new_button.click()
    _wait(qapp, lambda: not context.is_busy())
    assert context.active == "logistica" and combo.currentText() == "logistica"
    assert opened == [context.store.path("logistica")]
    editor.folder_button.click()
    assert len(opened) == 2
