"""
Lo que la web guarda por la API queda en `app_settings.json` (`setattr` y `save_app_config`)
y es lo que se lee con `load_app_config` al abrir de nuevo (FW.9).
Aquí ese archivo es uno temporal; sin red ni cupo.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="extra web: ./install.sh (jacck_common)")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.context import ContextLibrary  # noqa: E402
from app.live import LiveListening  # noqa: E402
from app.profiles import ProfileLibrary  # noqa: E402
from app.settings import ClaudeOptions  # noqa: E402
from config import AppConfig, load_app_config, save_app_config  # noqa: E402
from domain.claude.claude_account import AccountStatus  # noqa: E402
from domain.claude.claude_model import ClaudeModelConfig  # noqa: E402
from entrypoints.api.run import create_api  # noqa: E402
from services.service_contexts import ContextStore  # noqa: E402
from services.service_profiles import ProfileStore  # noqa: E402


class _NoEngine:
    def __init__(self, *_args):
        pass


def _open_api(tmp_path, settings_path):
    """La API como la arma `run_api`: lee el archivo y guarda cada cambio en él."""
    config = load_app_config(settings_path)

    def remember(key: str, value: object) -> None:
        setattr(config, key, value)
        save_app_config(config, settings_path)

    profiles_dir = tmp_path / "perfiles"
    profiles_dir.mkdir(exist_ok=True)
    for name in ("ejemplo", "empresa"):
        (profiles_dir / f"{name}.md").write_text(f"Perfil {name}.", encoding="utf-8")
    (tmp_path / "contextos" / "clientes").mkdir(parents=True, exist_ok=True)
    # Como `build_claude_options`: el perfil y el contexto recordados, y cada cambio guardado.
    options = ClaudeOptions(
        config=config.claude,
        save_config=lambda claude: remember("claude", claude),
        status_reader=lambda _exe, _folder: AccountStatus(True, email="", plan="max"),
        accounts_dir=tmp_path / "cuentas",
        profiles=ProfileLibrary(
            ProfileStore(profiles_dir),
            config.agent_profile,
            lambda name: remember("agent_profile", name),
        ),
        context=ContextLibrary(
            config.agent_context,
            lambda name: remember("agent_context", name),
            target=tmp_path / "contexto.md",
            store=ContextStore(tmp_path / "contextos"),
        ),
    )
    listening = LiveListening(lambda *_: _NoEngine(), tmp_path / "transcripciones")
    token = new_token()
    api = create_api(token, listening, options=options)
    client = TestClient(api, base_url="http://127.0.0.1")
    client.headers["Authorization"] = f"Bearer {token}"
    return client, options, listening


def test_what_the_web_saves_is_what_qt_reads(tmp_path) -> None:
    settings_path = tmp_path / "app_settings.json"
    client, options, listening = _open_api(tmp_path, settings_path)
    try:
        assert client.post("/api/settings/model", json={"value": "opus"}).status_code == 200
        assert client.post("/api/settings/effort", json={"value": "low"}).status_code == 200
        assert client.post("/api/settings/fallback", json={"value": "haiku"}).status_code == 200
        assert client.post("/api/settings/timeout", json={"seconds": 300}).status_code == 200
        profile = client.post("/api/profiles/active", json={"name": "empresa"})
        assert profile.status_code == 200
        context = client.post("/api/contexts/active", json={"name": "clientes"})
        assert context.status_code == 200
    finally:
        options.close()
        listening.close(5.0)
    # Lo que se lee al abrir de nuevo.
    saved = load_app_config(settings_path)
    assert (saved.agent_profile, saved.agent_context) == ("empresa", "clientes")
    claude = saved.claude
    assert (claude.model, claude.effort, claude.fallback_model, claude.timeout_s) == (
        "opus",
        "low",
        "haiku",
        300,
    )


def test_what_qt_saves_is_what_the_web_shows(tmp_path) -> None:
    settings_path = tmp_path / "app_settings.json"
    claude = ClaudeModelConfig(model="sonnet", effort="high", timeout_s=60)
    qt = AppConfig(claude=claude, agent_profile="empresa", agent_context="clientes")
    assert save_app_config(qt, settings_path)
    client, options, listening = _open_api(tmp_path, settings_path)
    try:
        shown = client.get("/api/settings").json()
    finally:
        options.close()
        listening.close(5.0)
    config = shown["config"]
    assert (config["model"], config["effort"], config["timeout_s"]) == ("sonnet", "high", 60)
    assert shown["profiles"]["active"] == "empresa"
    assert shown["contexts"]["active"] == "clientes"
