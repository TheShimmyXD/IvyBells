from __future__ import annotations

import time

from core.claude_account import AccountStatus
from core.claude_model import ClaudeModelConfig


def _wait(qapp, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition():
        qapp.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("se agotó la espera")
        time.sleep(0.01)


LOGGED_IN = AccountStatus(True, "persona@example.com", "pro")


def _settings(tmp_path, status=LOGGED_IN, **kwargs):
    from coordinator_config import ClaudeSettings

    saved: list[ClaudeModelConfig] = []
    calls: list[tuple] = []

    def reader(executable, config_dir):
        calls.append((executable, config_dir))
        return status

    settings = ClaudeSettings(
        ClaudeModelConfig(**kwargs), saved.append, reader, accounts_dir=tmp_path
    )
    return settings, saved, calls


def test_changes_are_saved_once(qapp, tmp_path):
    settings, saved, _calls = _settings(tmp_path)
    changed = []
    settings.config_changed.connect(changed.append)
    settings.set_model("opus")
    settings.set_model("opus")
    settings.set_effort("high")
    settings.set_timeout(300)
    settings.set_fallback("haiku")
    assert [c.model for c in saved] == ["opus", "opus", "opus", "opus"]
    assert saved[-1].effort == "high" and saved[-1].timeout_s == 300
    assert saved[-1].fallback_model == "haiku"
    assert len(changed) == 4


def test_invalid_account_is_rejected(qapp, tmp_path):
    settings, saved, _calls = _settings(tmp_path)
    got = []
    settings.account_checked.connect(got.append)
    assert not settings.set_account("no es correo")
    assert got[-1]["level"] == "error"
    assert saved == []


def test_check_reads_in_a_thread_and_reports(qapp, tmp_path):
    settings, _saved, calls = _settings(tmp_path)
    got = []
    settings.account_checked.connect(got.append)
    assert settings.set_account("persona@example.com")
    _wait(qapp, lambda: settings._thread is None and got[-1]["level"] != "busy")
    assert got[0]["level"] == "busy"
    assert got[-1] == {
        "text": "Sesión de persona@example.com (plan pro)",
        "level": "ok",
        "login": "",
    }
    assert calls == [("claude", None)]  # la sesión de siempre: sin carpeta propia
    assert not any(tmp_path.iterdir())


def test_other_account_gets_its_own_folder_and_login_command(qapp, tmp_path):
    settings, _saved, _calls = _settings(tmp_path, account="otra@example.com")
    got = []
    settings.account_checked.connect(got.append)
    settings.show_status(AccountStatus(True, "persona@example.com", "pro"))
    folder = tmp_path / "otra@example.com"
    assert folder.is_dir()
    assert got[-1]["level"] == "warning"
    assert got[-1]["login"].startswith(f"CLAUDE_CONFIG_DIR={folder}")
    assert settings.config_dir() == folder


def test_default_session_without_login_never_gets_a_folder(qapp, tmp_path):
    settings, _saved, _calls = _settings(tmp_path)
    got = []
    settings.account_checked.connect(got.append)
    settings.show_status(AccountStatus(False))
    assert got[-1]["login"] == "claude auth login"
    assert not any(tmp_path.iterdir())
