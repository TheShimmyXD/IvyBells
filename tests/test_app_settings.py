"""Configuración, perfiles y contexto sin Qt: los avisos de los hilos llegan por `post`."""

from __future__ import annotations

import queue
import threading

from app.context import ContextLibrary, ContextListeners
from app.profiles import ProfileLibrary
from app.settings import ClaudeOptions, SettingsListeners
from domain.claude.claude_account import AccountStatus
from domain.claude.claude_model import ClaudeModelConfig
from services.service_context import write_context
from services.service_contexts import ContextStore
from services.service_profiles import ProfileStore


def _drain(tasks, done, timeout_s=5.0):
    """Corre en este hilo (el dueño) lo que llega por `post`, hasta que `done()`."""
    while not done():
        tasks.get(timeout=timeout_s)()


def test_context_photo_arrives_in_the_owner_thread(tmp_path):
    store = ContextStore(tmp_path / "contextos")
    (store.path(store.create("empresa")) / "servicios.md").write_text("Plan", encoding="utf-8")
    owner = threading.get_ident()
    tasks, notices, writers = queue.Queue(), [], []

    def on_reloaded(payload):
        assert threading.get_ident() == owner
        notices.append(payload)

    def writer(paths, target):
        writers.append(threading.get_ident())
        return write_context(paths, target)

    context = ContextLibrary(target=tmp_path / "contexto.md", writer=writer, store=store)
    context.attach(tasks.put, ContextListeners(reloaded=on_reloaded))
    context.set_active("empresa")
    context.reload()  # mientras lee: se lee otra vez al terminar
    _drain(tasks, lambda: len(notices) == 4 and not context.is_busy())

    assert [n["level"] for n in notices] == ["busy", "ok", "busy", "ok"]
    assert notices[-1]["text"].endswith("(sin cambios)")
    assert len(writers) == 2 and owner not in writers
    assert "Plan" in context.text()


def test_account_check_and_profiles_without_qt(tmp_path):
    owner = threading.get_ident()
    tasks, got, threads = queue.Queue(), [], []

    def reader(executable, folder):
        threads.append(threading.get_ident())
        return AccountStatus(True, "persona@example.com", "pro")

    def on_account(payload):
        assert threading.get_ident() == owner
        got.append(payload)

    folder = tmp_path / "perfiles"
    folder.mkdir()
    (folder / "acme.md").write_text("Soy de Acme.", encoding="utf-8")
    options = ClaudeOptions(
        ClaudeModelConfig(),
        status_reader=reader,
        accounts_dir=tmp_path,
        profiles=ProfileLibrary(ProfileStore(folder), "acme"),
        context=ContextLibrary(target=tmp_path / "contexto.md", store=ContextStore(tmp_path)),
    )
    options.attach(tasks.put, SettingsListeners(account=on_account))
    options.check()
    _drain(tasks, lambda: not options.is_busy())

    assert [g["level"] for g in got] == ["busy", "ok"]
    assert len(threads) == 1 and threads[0] != owner
    assert "Soy de Acme." in options.profiles.system_prompt("")
    options.close()
