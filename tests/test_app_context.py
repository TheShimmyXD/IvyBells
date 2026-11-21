"""Contexto del agente sin Qt (`app.context.ContextLibrary`); antes, por su adaptador Qt.

Los avisos del hilo que lee llegan por `post` a una cola y los corre el hilo de la prueba,
el dueño: con `call_now` el hilo podria terminar antes de que `reload` guarde su referencia.
"""

from __future__ import annotations

import contextlib
import queue
import threading
import time

import pytest

from app.context import ContextLibrary, ContextListeners
from services.service_context import write_context
from services.service_contexts import ContextStore


def _owned(context: ContextLibrary) -> ContextLibrary:
    context.tasks = queue.Queue()
    context.attach(context.tasks.put, context.listeners)
    return context


def _wait(context, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("se agotó la espera")
        with contextlib.suppress(queue.Empty):
            context.tasks.get(timeout=0.01)()


def _reload(context):
    context.reload()
    _wait(context, lambda: not context.is_busy())


def _listen(context, **listeners) -> None:
    context.listeners = ContextListeners(**listeners)


@pytest.fixture
def context(tmp_path):
    store = ContextStore(tmp_path / "contextos")
    folder = store.path(store.create("empresa"))
    (folder / "servicios.md").write_text("Plan básico", encoding="utf-8")
    (folder / "catalogo.pdf").write_bytes(b"%PDF")
    saved = []
    library = _owned(ContextLibrary("", saved.append, target=tmp_path / "contexto.md", store=store))
    library.saved = saved
    yield library
    library.close()


def test_set_active_remembers_and_reloads(context):
    notices = []
    _listen(context, reloaded=notices.append)
    context.set_active("no_existe")
    assert context.active == "" and context.paths == [] and context.saved == []
    context.set_active("empresa")
    _wait(context, lambda: not context.is_busy())
    assert context.saved == ["empresa"]
    assert context.paths == [str(context.store.path("empresa"))]
    assert [n["level"] for n in notices] == ["busy", "warning"]
    assert "1 archivos" in notices[-1]["text"] and "catalogo.pdf" in notices[-1]["text"]
    assert "Plan básico" in context.text()
    weights = context.weights()
    assert weights[str(context.folder / "servicios.md")] > 0
    assert weights[str(context.folder / "catalogo.pdf")] == 0
    _reload(context)
    assert notices[-1]["text"].endswith("(sin cambios)")
    context.set_active("")
    _wait(context, lambda: not context.is_busy())
    assert context.saved == ["empresa", ""] and context.text() == ""


def test_remembered_context_that_no_longer_exists(tmp_path):
    context = ContextLibrary(
        "borrado", target=tmp_path / "contexto.md", store=ContextStore(tmp_path)
    )
    assert context.active == "" and context.folder is None and context.weights() == {}


def test_create_and_rename(context):
    changes = []
    _listen(context, changed=lambda: changes.append("lista"))
    assert context.create("entrevista") == "entrevista"
    _wait(context, lambda: not context.is_busy())
    assert context.active == "entrevista" and context.saved == ["entrevista"]
    assert context.rename("entrevista", "logistica") == "logistica"
    _wait(context, lambda: not context.is_busy())
    assert context.active == "logistica" and context.saved[-1] == "logistica"
    assert context.rename("empresa", "otra") == "otra" and context.active == "logistica"
    assert changes == ["lista"] * 3


def test_errors_go_to_the_status(context):
    notices = []
    _listen(context, reloaded=notices.append)
    assert context.create("empresa") == ""
    assert context.rename("empresa", "///") == ""
    assert [n["level"] for n in notices] == ["error", "error"]


def test_no_context(context):
    notices = []
    _listen(context, reloaded=notices.append)
    _reload(context)
    assert notices[-1]["level"] == "info"
    assert context.text() == ""


def test_reload_does_not_block_and_queues_one_more(tmp_path):
    release = threading.Event()
    calls = []

    def slow_writer(paths, target):
        calls.append(list(paths))
        release.wait(5)
        return write_context(paths, target)

    store = ContextStore(tmp_path / "contextos")
    store.create("a")
    store.create("b")
    context = _owned(
        ContextLibrary("a", target=tmp_path / "contexto.md", writer=slow_writer, store=store)
    )
    started = time.monotonic()
    context.reload()
    assert time.monotonic() - started < 0.5 and context.is_busy()
    context.set_active("b")
    context.reload()
    release.set()
    _wait(context, lambda: len(calls) == 2 and not context.is_busy())
    assert calls == [[str(store.path("a"))], [str(store.path("b"))]]
    context.close()


def test_writer_error_is_reported(tmp_path):
    def broken(paths, target):
        raise OSError("disco lleno")

    context = _owned(
        ContextLibrary(
            target=tmp_path / "contexto.md", writer=broken, store=ContextStore(tmp_path / "c")
        )
    )
    notices = []
    _listen(context, reloaded=notices.append)
    _reload(context)
    assert notices[-1] == {"text": "No se pudo rehacer contexto.md: disco lleno", "level": "error"}
