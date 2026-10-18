from __future__ import annotations

import json

from config import AppConfig, load_app_config, save_app_config
from core.claude_model import ClaudeModelConfig, is_valid_model


def test_defaults_give_sonnet_without_extra_flags():
    assert ClaudeModelConfig().cli_args() == ["--model", "sonnet"]


def test_aliases_and_full_names_are_valid():
    assert is_valid_model("opus")
    assert is_valid_model("claude-sonnet-5-5")
    assert not is_valid_model("gpt-4")
    assert not is_valid_model("claude-")
    assert not is_valid_model("")


def test_invalid_values_fall_back_to_defaults():
    config = ClaudeModelConfig.from_dict(
        {"model": "gpt-4", "effort": "turbo", "timeout_s": -5, "fallback_model": "x"}
    )
    assert config == ClaudeModelConfig()


def test_not_a_dict_gives_defaults():
    assert ClaudeModelConfig.from_dict(None) == ClaudeModelConfig()
    assert ClaudeModelConfig.from_dict(["opus"]) == ClaudeModelConfig()


def test_values_are_normalized():
    config = ClaudeModelConfig.from_dict({"model": "  Opus ", "effort": "HIGH"})
    assert config.model == "opus"
    assert config.effort == "high"


def test_cli_args_with_effort_and_fallback():
    config = ClaudeModelConfig(model="opus", effort="high", fallback_model="sonnet")
    assert config.cli_args() == [
        "--model",
        "opus",
        "--effort",
        "high",
        "--fallback-model",
        "sonnet",
    ]


def test_fallback_equal_to_model_is_skipped():
    config = ClaudeModelConfig(model="sonnet", fallback_model="sonnet")
    assert "--fallback-model" not in config.cli_args()


def test_round_trip_inside_app_config(tmp_path):
    path = tmp_path / "settings.json"
    claude = ClaudeModelConfig(model="haiku", effort="low", timeout_s=60)
    assert save_app_config(AppConfig(claude=claude), path)
    assert load_app_config(path).claude == claude
    assert json.loads(path.read_text(encoding="utf-8"))["claude"]["model"] == "haiku"


def test_old_settings_without_claude_key_get_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    config = load_app_config(path)
    assert config.theme == "dark"
    assert config.claude == ClaudeModelConfig()
