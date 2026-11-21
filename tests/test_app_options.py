"""Modelo y cuenta de Claude (`app.settings.ClaudeOptions`); antes, por su adaptador Qt."""

from __future__ import annotations

import queue

from app.context import ContextLibrary
from app.profiles import ProfileLibrary
from app.settings import ClaudeOptions, SettingsListeners
from domain.claude.claude_account import AccountStatus
from domain.claude.claude_model import ClaudeModelConfig
from services.service_contexts import ContextStore
from services.service_profiles import ProfileStore

LOGGED_IN = AccountStatus(True, "persona@example.com", "pro")


def _options(tmp_path, status=LOGGED_IN, **kwargs):
    saved: list[ClaudeModelConfig] = []
    calls: list[tuple] = []
    got = {"config": [], "account": []}

    def reader(executable, config_dir):
        calls.append((executable, config_dir))
        return status

    accounts = tmp_path / "cuentas"
    accounts.mkdir()
    options = ClaudeOptions(
        ClaudeModelConfig(**kwargs),
        saved.append,
        reader,
        accounts_dir=accounts,
        profiles=ProfileLibrary(ProfileStore(tmp_path / "perfiles")),
        context=ContextLibrary(target=tmp_path / "contexto.md", store=ContextStore(tmp_path)),
    )
    options.listeners = SettingsListeners(
        config=got["config"].append, account=got["account"].append
    )
    return options, saved, calls, got, accounts


def test_changes_are_saved_once(tmp_path):
    options, saved, _calls, got, _accounts = _options(tmp_path)
    options.set_model("opus")
    options.set_model("opus")
    options.set_effort("high")
    options.set_timeout(300)
    options.set_fallback("haiku")
    assert [c.model for c in saved] == ["opus", "opus", "opus", "opus"]
    assert saved[-1].effort == "high" and saved[-1].timeout_s == 300
    assert saved[-1].fallback_model == "haiku"
    assert len(got["config"]) == 4


def test_invalid_account_is_rejected(tmp_path):
    options, saved, _calls, got, _accounts = _options(tmp_path)
    assert not options.set_account("no es correo")
    assert got["account"][-1]["level"] == "error"
    assert saved == []


def test_check_reads_in_a_thread_and_reports(tmp_path):
    options, _saved, calls, got, accounts = _options(tmp_path)
    # El aviso del hilo llega por `post` y lo corre este hilo, el dueño.
    tasks: queue.Queue = queue.Queue()
    options.attach(tasks.put, options.listeners)
    assert options.set_account("persona@example.com")
    while options.is_busy():
        tasks.get(timeout=5.0)()
    assert got["account"][0]["level"] == "busy"
    assert got["account"][-1] == {
        "text": "Sesión de persona@example.com (plan pro)",
        "level": "ok",
        "login": "",
    }
    assert calls == [("claude", None)]  # la sesión de siempre: sin carpeta propia
    assert not any(accounts.iterdir())
    options.close()


def test_other_account_gets_its_own_folder_and_login_command(tmp_path):
    options, _saved, _calls, got, accounts = _options(tmp_path, account="otra@example.com")
    options.show_status(AccountStatus(True, "persona@example.com", "pro"))
    folder = accounts / "otra@example.com"
    assert folder.is_dir()
    assert got["account"][-1]["level"] == "warning"
    assert got["account"][-1]["login"].startswith(f"CLAUDE_CONFIG_DIR={folder}")
    assert options.config_dir() == folder


def test_default_session_without_login_never_gets_a_folder(tmp_path):
    options, _saved, _calls, got, accounts = _options(tmp_path)
    options.show_status(AccountStatus(False))
    assert got["account"][-1]["login"] == "claude auth login"
    assert not any(accounts.iterdir())
