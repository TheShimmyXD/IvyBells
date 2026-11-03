from __future__ import annotations

import pytest

from core.agent_context import ContextError
from services.service_contexts import ContextStore


def test_names_are_folders_in_order(tmp_path):
    store = ContextStore(tmp_path / "contextos")
    assert store.names() == []
    store.create("TodoApp")
    store.create("entrevista")
    (store.folder / "suelto.md").write_text("no es contexto", encoding="utf-8")
    assert store.names() == ["entrevista", "TodoApp"]


def test_create_cleans_and_rejects_repeated_names(tmp_path):
    store = ContextStore(tmp_path)
    assert store.create("  cruz/roja  ") == "cruzroja"
    with pytest.raises(ContextError, match="Ya hay"):
        store.create("CRUZROJA")
    with pytest.raises(ContextError):
        store.create("///")


def test_rename_keeps_the_files(tmp_path):
    store = ContextStore(tmp_path)
    store.create("viejo")
    (store.path("viejo") / "a.md").write_text("hola", encoding="utf-8")
    store.create("otro")
    assert store.rename("viejo", "nuevo") == "nuevo"
    assert (store.path("nuevo") / "a.md").read_text(encoding="utf-8") == "hola"
    with pytest.raises(ContextError, match="Ya hay"):
        store.rename("nuevo", "otro")
    assert store.rename("nuevo", "Nuevo") == "Nuevo"


def test_entries(tmp_path):
    store = ContextStore(tmp_path)
    store.create("c")
    (store.path("c") / "b.md").write_text("", encoding="utf-8")
    (store.path("c") / "A").mkdir()
    assert [path.name for path in store.entries("c")] == ["A", "b.md"]
    assert store.entries("") == [] and store.entries("no_existe") == []
