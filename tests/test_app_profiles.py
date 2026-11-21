"""Perfiles del agente sin Qt (`app.profiles.ProfileLibrary`); antes, por su adaptador Qt."""

from __future__ import annotations

import pytest

from app.profiles import ProfileLibrary, ProfileListeners
from domain.agent.agent_profile import FIXED_RULES
from services.service_profiles import ProfileStore


@pytest.fixture
def profiles(tmp_path):
    folder = tmp_path / "perfiles"
    folder.mkdir()
    (folder / "ejemplo.md").write_text("de ejemplo", encoding="utf-8")
    saved: list[str] = []
    library = ProfileLibrary(ProfileStore(folder), "empresa", saved.append)
    library.saved = saved
    return library


def test_missing_active_falls_back_to_example(profiles):
    assert profiles.active == "ejemplo"
    assert "de ejemplo" in profiles.system_prompt()


def test_no_profiles_means_rules_only(tmp_path):
    library = ProfileLibrary(ProfileStore(tmp_path / "vacia"))
    assert library.active == ""
    assert library.system_prompt().startswith(FIXED_RULES)
    assert "<perfil>" not in library.system_prompt()


def test_set_active_is_remembered_and_used(profiles):
    name = profiles.duplicate("ejemplo")
    assert name == "ejemplo copia"
    changes = []
    profiles.listeners = ProfileListeners(active=changes.append)
    profiles.set_active(name)
    assert profiles.active == name and changes == [name]
    assert profiles.saved == [name]
    profiles.save(name, "Somos Acme.")
    assert "Somos Acme." in profiles.system_prompt()


def test_rename_keeps_the_active_one(profiles):
    name = profiles.create()
    profiles.set_active(name)
    assert profiles.rename(name, "acme") == "acme"
    assert profiles.active == "acme"
    assert profiles.saved[-1] == "acme"


def test_delete_active_falls_back(profiles):
    name = profiles.create()
    profiles.set_active(name)
    changes = []
    profiles.listeners = ProfileListeners(active=changes.append)
    assert profiles.delete(name)
    assert profiles.active == "ejemplo"
    assert changes == ["ejemplo"]


def test_errors_go_to_notice(profiles):
    notices = []
    profiles.listeners = ProfileListeners(notice=notices.append)
    assert not profiles.save("ejemplo", "otro")
    assert profiles.rename(profiles.create(), "   ") == ""
    assert [notice["level"] for notice in notices] == ["error", "error"]
