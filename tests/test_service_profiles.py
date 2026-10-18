from __future__ import annotations

import pytest

from core.agent_profile import ProfileError
from paths import AGENT_PROFILES_DIR
from services.service_profiles import ProfileStore, write_if_changed


@pytest.fixture
def store(tmp_path):
    folder = tmp_path / "perfiles"
    folder.mkdir()
    (folder / "ejemplo.md").write_text("de ejemplo", encoding="utf-8")
    return ProfileStore(folder)


def test_example_goes_first(store):
    store.create("zeta")
    store.create("Alfa")
    assert store.names() == ["ejemplo", "Alfa", "zeta"]


def test_missing_folder_lists_nothing(tmp_path):
    assert ProfileStore(tmp_path / "no_existe").names() == []


def test_create_save_read(store):
    name = store.create("  Empresa  ", "hola")
    assert name == "Empresa"
    store.save(name, "texto nuevo")
    assert store.read(name) == "texto nuevo"


def test_create_rejects_a_taken_name(store):
    store.create("empresa")
    with pytest.raises(ProfileError, match="Ya hay"):
        store.create("EMPRESA")


def test_rename_and_delete(store):
    store.create("empresa", "x")
    assert store.rename("empresa", "ventas") == "ventas"
    assert store.read("ventas") == "x"
    assert "empresa" not in store.names()
    store.delete("ventas")
    assert store.names() == ["ejemplo"]


def test_rename_only_case(store):
    store.create("empresa")
    assert store.rename("empresa", "Empresa") == "Empresa"
    assert store.names() == ["ejemplo", "Empresa"]


@pytest.mark.parametrize("action", ["save", "rename", "delete"])
def test_example_is_protected(store, action):
    calls = {
        "save": lambda: store.save("ejemplo", "otro"),
        "rename": lambda: store.rename("ejemplo", "otro"),
        "delete": lambda: store.delete("ejemplo"),
    }
    with pytest.raises(ProfileError, match="duplícalo"):
        calls[action]()
    assert store.read("ejemplo") == "de ejemplo"


def test_adopt_legacy_moves_it_once(store, tmp_path):
    legacy = tmp_path / "perfil_local.md"
    legacy.write_text("de la empresa", encoding="utf-8")
    assert store.adopt_legacy(legacy) == "local"
    assert store.read("local") == "de la empresa"
    assert not legacy.exists()
    assert store.adopt_legacy(legacy) == ""


def test_adopt_legacy_keeps_an_existing_local(store, tmp_path):
    store.create("local", "ya estaba")
    legacy = tmp_path / "perfil_local.md"
    legacy.write_text("de antes", encoding="utf-8")
    assert store.adopt_legacy(legacy) == ""
    assert store.read("local") == "ya estaba"
    assert legacy.exists()


def test_write_if_changed(tmp_path):
    path = tmp_path / "neutral" / "system_prompt.md"
    assert write_if_changed(path, "a")
    assert not write_if_changed(path, "a")
    assert write_if_changed(path, "b")
    assert path.read_text(encoding="utf-8") == "b"


def test_versioned_example_has_no_fixed_rules():
    text = (AGENT_PROFILES_DIR / "ejemplo.md").read_text(encoding="utf-8")
    assert text.strip()
    assert "<cliente>" not in text
