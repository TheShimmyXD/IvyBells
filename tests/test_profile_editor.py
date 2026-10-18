from __future__ import annotations

import pytest

from coordinator_profiles import AgentProfiles
from services.service_profiles import ProfileStore


@pytest.fixture
def editor(qapp, tmp_path, monkeypatch):
    import ui.profile_editor as module

    folder = tmp_path / "perfiles"
    folder.mkdir()
    (folder / "ejemplo.md").write_text("de ejemplo", encoding="utf-8")
    answers = {"confirm": True, "name": "acme"}
    monkeypatch.setattr(module, "confirm", lambda *_args: answers["confirm"])
    monkeypatch.setattr(module, "ask_name", lambda *_args: answers["name"])
    widget = module.ProfileEditor(AgentProfiles(ProfileStore(folder)))
    widget.answers = answers
    return widget


def test_example_is_read_only(editor):
    assert editor.current == "ejemplo"
    assert editor.editor.isReadOnly()
    assert not editor.save_button.isEnabled()
    assert not editor.delete_button.isEnabled()
    assert not editor.rename_button.isEnabled()
    assert editor.duplicate_button.isEnabled()
    assert "(en uso)" in editor.list.item(0).text()


def test_new_edit_save_and_use(editor):
    editor.new_button.click()
    assert editor.current == "nuevo perfil"
    assert not editor.editor.isReadOnly()
    editor.editor.insertPlainText("Somos Acme.")
    assert editor.save_button.isEnabled()
    editor.save_button.click()
    assert editor.profiles.text("nuevo perfil") == "Somos Acme."
    assert not editor.save_button.isEnabled()
    editor.use_button.click()
    assert editor.profiles.active == "nuevo perfil"
    assert not editor.use_button.isEnabled()


def test_switching_with_changes_asks_to_save(editor):
    editor.new_button.click()
    editor.editor.insertPlainText("sin guardar")
    editor.select("ejemplo")
    assert editor.profiles.text("nuevo perfil") == "sin guardar"


def test_rename_and_delete(editor):
    editor.duplicate_button.click()
    editor.rename_button.click()
    assert editor.current == "acme"
    assert editor.profiles.text("acme") == "de ejemplo"
    editor.answers["confirm"] = False
    editor.delete_button.click()
    assert "acme" in editor.profiles.names()
    editor.answers["confirm"] = True
    editor.delete_button.click()
    assert editor.profiles.names() == ["ejemplo"]
    assert editor.current == "ejemplo"
