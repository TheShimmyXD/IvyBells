from __future__ import annotations

import pytest

from coordinator_profiles import AgentProfiles
from core.agent_profile import FIXED_RULES
from services.service_profiles import ProfileStore


@pytest.fixture
def profiles(qapp, tmp_path):
    folder = tmp_path / "perfiles"
    folder.mkdir()
    (folder / "ejemplo.md").write_text("de ejemplo", encoding="utf-8")
    saved: list[str] = []
    coordinator = AgentProfiles(ProfileStore(folder), "empresa", saved.append)
    coordinator.saved = saved
    return coordinator


def test_missing_active_falls_back_to_example(profiles):
    assert profiles.active == "ejemplo"
    assert "de ejemplo" in profiles.system_prompt()


def test_no_profiles_means_rules_only(qapp, tmp_path):
    coordinator = AgentProfiles(ProfileStore(tmp_path / "vacia"))
    assert coordinator.active == ""
    assert coordinator.system_prompt().startswith(FIXED_RULES)
    assert "<perfil>" not in coordinator.system_prompt()


def test_set_active_is_remembered_and_used(profiles):
    name = profiles.duplicate("ejemplo")
    assert name == "ejemplo copia"
    changes = []
    profiles.active_changed.connect(changes.append)
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
    profiles.active_changed.connect(changes.append)
    assert profiles.delete(name)
    assert profiles.active == "ejemplo"
    assert changes == ["ejemplo"]


def test_errors_go_to_notice(profiles):
    notices = []
    profiles.notice.connect(notices.append)
    assert not profiles.save("ejemplo", "otro")
    assert profiles.rename(profiles.create(), "   ") == ""
    assert [notice["level"] for notice in notices] == ["error", "error"]
