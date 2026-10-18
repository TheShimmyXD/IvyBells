from __future__ import annotations

import os
import sys
from pathlib import Path

from core.claude_account import AccountStatus, account_slug, describe, parse_status
from core.claude_model import ClaudeModelConfig, clean_account
from services.service_claude_account import (
    claude_env,
    config_dir_for,
    login_command,
    prepare_account_dir,
    read_status,
)

FIXTURES = Path(__file__).parent / "fixtures" / "claude"


def test_real_samples_parse():
    status = parse_status((FIXTURES / "auth_status.json").read_text(encoding="utf-8"))
    assert status == AccountStatus(True, "persona@example.com", "pro", "/home/usuario/.claude")
    empty = parse_status((FIXTURES / "auth_status_sin_sesion.json").read_text(encoding="utf-8"))
    assert not empty.logged_in and empty.email == "" and not empty.error


def test_unreadable_output_is_an_error():
    assert parse_status("").error
    assert parse_status("[1]").error


def test_describe_levels():
    ok = AccountStatus(True, "persona@example.com", "pro")
    assert describe(ok, "") == ("Sesión de persona@example.com (plan pro)", "ok")
    assert describe(ok, "persona@example.com")[1] == "ok"
    assert describe(ok, "otra@example.com") == (
        "La sesión es de persona@example.com, no de otra@example.com",
        "warning",
    )
    assert describe(AccountStatus(False), "otra@example.com")[1] == "warning"
    assert describe(AccountStatus(False, error="x"), "")[1] == "error"


def test_account_is_cleaned():
    assert clean_account("  Persona@Example.com ") == "persona@example.com"
    assert clean_account("no es correo") == ""
    assert clean_account("a@b") == ""
    assert clean_account("../x@y.com") == ""
    config = ClaudeModelConfig.from_dict({"account": "Otra@Example.com"})
    assert config.account == "otra@example.com"
    assert ClaudeModelConfig.from_dict({"account": "basura"}).account == ""


def test_slug_keeps_folder_names_safe():
    assert account_slug("Persona+demo@Example.com") == "persona_demo@example.com"


def test_config_dir_only_when_its_folder_exists(tmp_path):
    assert config_dir_for("", tmp_path) is None
    assert config_dir_for("otra@example.com", tmp_path) is None
    folder = prepare_account_dir("otra@example.com", tmp_path)
    assert config_dir_for("otra@example.com", tmp_path) == folder
    assert claude_env(None) is None
    assert claude_env(folder)["CLAUDE_CONFIG_DIR"] == str(folder)


def test_login_command_is_ready_to_paste(tmp_path):
    folder = tmp_path / "con espacio"
    assert login_command("claude", "", None) == "claude auth login"
    assert login_command("claude", "otra@example.com", folder) == (
        f"CLAUDE_CONFIG_DIR='{folder}' claude auth login --email otra@example.com"
    )


def test_read_status_uses_the_account_folder(tmp_path):
    # CLI falsa que responde con la carpeta que recibió en el entorno.
    script = tmp_path / "fake_claude"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os\n"
        "print(json.dumps({'loggedIn': True, 'email': 'otra@example.com',\n"
        "                  'configDirectory': os.environ.get('CLAUDE_CONFIG_DIR', '')}))\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    folder = prepare_account_dir("otra@example.com", tmp_path)
    status = read_status(str(script), folder)
    assert status.logged_in and status.config_dir == str(folder)
    assert read_status(str(tmp_path / "no_existe"), None).error
    assert "CLAUDE_CONFIG_DIR" not in (claude_env(None) or os.environ)
