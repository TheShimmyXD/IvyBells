"""Configuración, cuenta, perfiles, contextos y lo recordado por la API (sin red ni cupo)."""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("fastapi", reason="extra web: pip install -e '../jacck_common[webapi]'")

from fastapi.testclient import TestClient  # noqa: E402
from jacck_common.webapi.security import new_token  # noqa: E402

from app.agent import AgentAssistant  # noqa: E402
from app.chat import ChatAssistant  # noqa: E402
from app.context import ContextLibrary  # noqa: E402
from app.live import LiveListening  # noqa: E402
from app.profiles import ProfileLibrary  # noqa: E402
from app.settings import ClaudeOptions  # noqa: E402
from domain.claude.claude_account import AccountStatus  # noqa: E402
from entrypoints.api.prefs import Prefs  # noqa: E402
from entrypoints.api.run import create_api  # noqa: E402
from services.service_claude import ScriptedClaude  # noqa: E402
from services.service_context import ContextReport  # noqa: E402
from services.service_contexts import ContextStore  # noqa: E402
from services.service_profiles import ProfileStore  # noqa: E402

ACCOUNT = "autor@ejemplo.com"


class _NoEngine:
    def __init__(self, *_args):
        pass


def _writer(paths: list[str], target) -> ContextReport:
    target.write_text("\n".join(paths), encoding="utf-8")
    return ContextReport(files=len(paths), chars=10, omitted=[], changed=True)


@pytest.fixture
def setup(tmp_path):
    profiles_dir = tmp_path / "perfiles"
    profiles_dir.mkdir()
    (profiles_dir / "ejemplo.md").write_text("Perfil de ejemplo.", encoding="utf-8")
    (tmp_path / "contextos").mkdir()
    remembered: list[tuple[str, object]] = []

    def remember(key: str, value: object) -> None:
        remembered.append((key, value))

    options = ClaudeOptions(
        save_config=lambda config: remember("claude", config.to_dict()),
        status_reader=lambda _exe, _folder: AccountStatus(True, email=ACCOUNT, plan="max"),
        accounts_dir=tmp_path / "cuentas",
        profiles=ProfileLibrary(
            ProfileStore(profiles_dir), save_active=lambda n: remember("agent_profile", n)
        ),
        context=ContextLibrary(
            save_active=lambda n: remember("agent_context", n),
            target=tmp_path / "contexto.md",
            writer=_writer,
            store=ContextStore(tmp_path / "contextos"),
        ),
    )
    listening = LiveListening(lambda *_: _NoEngine(), tmp_path / "transcripciones")
    agent = AgentAssistant(listening, options, lambda *_: ScriptedClaude(["Hola."]))
    chat = ChatAssistant(listening, options, service_factory=lambda *_: ScriptedClaude(["Ok."]))
    yield listening, agent, chat, options, remembered
    agent.close()
    chat.close()
    options.close()
    listening.close(5.0)


def _client(setup, token, prefs=None):
    listening, agent, chat, options, _ = setup
    api = create_api(token, listening, agent, chat, 0.05, options=options, prefs=prefs)
    return api, TestClient(api, base_url="http://127.0.0.1")


def _until(read, condition, timeout_s: float = 5.0):
    deadline = time.monotonic() + timeout_s
    value = read()
    while not condition(value) and time.monotonic() < deadline:
        time.sleep(0.02)
        value = read()
    return value


def _kinds(text: str) -> list[tuple[str, dict]]:
    frames = []
    for block in text.strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
        )
        if fields:
            frames.append((fields["event"], json.loads(fields["data"])))
    return frames


def test_model_change_is_saved_and_reaches_the_chat(setup) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    api, client = _client(setup, token)
    remembered = setup[4]
    with client:
        assert client.get("/api/settings").status_code == 401
        changed = client.post("/api/settings/model", headers=headers, json={"value": "haiku"})
        assert changed.json()["model"] == "haiku"
        assert client.post(
            "/api/settings/effort", headers=headers, json={"value": "max"}
        ).is_success
        for route, body in (
            ("model", {"value": "gpt"}),
            ("effort", {"value": "ultra"}),
            ("fallback", {"value": "otro"}),
            ("timeout", {"seconds": 45}),
        ):
            assert (
                client.post(f"/api/settings/{route}", headers=headers, json=body).status_code == 422
            )
        snapshot = client.get("/api/settings", headers=headers)
        api.state.settings_channel.close("closed", {})
        api.state.chat_channel.close("closed", {})
        settings_stream = client.get("/api/settings/events", headers=headers).text
        chat_stream = client.get("/api/chat/events", headers=headers).text

    data = snapshot.json()
    assert data["config"]["model"] == "haiku" and data["config"]["effort"] == "max"
    assert [m["key"] for m in data["choices"]["models"]] == ["haiku", "sonnet", "opus"]
    assert token not in snapshot.text
    assert [value["effort"] for key, value in remembered if key == "claude"] == ["", "max"]
    assert [d["model"] for k, d in _kinds(settings_stream) if k == "config"] == ["haiku", "haiku"]
    # El chat oye el cambio, como en la ventana (`on_settings_changed`).
    assert "config" in [kind for kind, _ in _kinds(chat_stream)]


def test_account_is_checked_in_its_thread_and_reported(setup) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    _, client = _client(setup, token)
    with client:
        bad = client.post("/api/settings/account", headers=headers, json={"value": "no-correo"})
        assert bad.status_code == 422 and "no parece un correo" in bad.json()["detail"]
        ok = client.post("/api/settings/account", headers=headers, json={"value": ACCOUNT})
        assert ok.json()["account"] == ACCOUNT
        state = _until(
            lambda: client.get("/api/settings", headers=headers).json(),
            lambda s: s["account"]["level"] not in ("busy", "info"),
        )
    assert state["account"]["level"] == "ok"
    assert not state["checking"]


def test_profiles_are_created_edited_renamed_and_deleted(setup) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    _, client = _client(setup, token)
    remembered = setup[4]
    with client:
        name = client.post("/api/profiles", headers=headers).json()["name"]
        assert name == "nuevo perfil"
        saved = client.put(f"/api/profiles/{name}", headers=headers, json={"text": "Breve."})
        assert saved.status_code == 200
        assert client.get(f"/api/profiles/{name}", headers=headers).json()["text"] == "Breve."
        renamed = client.post(
            f"/api/profiles/{name}/rename", headers=headers, json={"name": "empresa"}
        ).json()
        assert renamed["name"] == "empresa" and "empresa" in renamed["names"]
        active = client.post("/api/profiles/active", headers=headers, json={"name": "empresa"})
        assert active.json()["active"] == "empresa"
        locked = client.put("/api/profiles/ejemplo", headers=headers, json={"text": "x"})
        missing = client.get("/api/profiles/nadie", headers=headers)
        after = client.delete("/api/profiles/empresa", headers=headers).json()

    assert locked.status_code == 409 and locked.json()["detail"]
    assert missing.status_code == 404
    assert after["active"] == "ejemplo" and after["names"] == ["ejemplo"]
    assert [v for k, v in remembered if k == "agent_profile"] == ["empresa", "ejemplo"]


def test_context_is_created_and_its_photo_reaches_the_agent(setup) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    api, client = _client(setup, token)
    remembered = setup[4]
    with client:
        created = client.post("/api/contexts", headers=headers, json={"name": "clientes"}).json()
        assert created["name"] == "clientes" and created["active"] == "clientes"
        _until(
            lambda: client.get("/api/settings", headers=headers).json(),
            lambda s: not s["contexts"]["busy"],
        )
        missing = client.post("/api/contexts/active", headers=headers, json={"name": "nadie"})
        none = client.post("/api/contexts/active", headers=headers, json={"name": ""}).json()
        _until(
            lambda: client.get("/api/settings", headers=headers).json(),
            lambda s: not s["contexts"]["busy"],
        )
        api.state.settings_channel.close("closed", {})
        stream = client.get("/api/settings/events", headers=headers).text

    assert missing.status_code == 404
    assert none["active"] == "" and none["folder"] is None
    reloaded = [data["level"] for kind, data in _kinds(stream) if kind == "context_reloaded"]
    assert reloaded[:2] == ["busy", "ok"] and reloaded[-1] == "info"
    assert [v for k, v in remembered if k == "agent_context"] == ["clientes", ""]


def test_remembered_speaker_and_mode_and_view_prefs(setup) -> None:
    token = new_token()
    headers = {"Authorization": f"Bearer {token}"}
    saved: list[tuple[str, object]] = []
    prefs = Prefs({"speaker": "tu", "agent_mode": "ahead"}, lambda k, v: saved.append((k, v)))
    _, client = _client(setup, token, prefs)
    with client:
        agent = client.get("/api/agent", headers=headers).json()
        assert (agent["speaker"], agent["mode"]) == ("tu", "ahead")
        client.post("/api/agent/mode", headers=headers, json={"mode": "manual"})
        client.post("/api/agent/speaker", headers=headers, json={"source": "ellos"})
        client.post("/api/listening/sources/tu", headers=headers, json={"open": False})
        client.post("/api/prefs", headers=headers, json={"key": "theme", "value": "dark"})
        unknown = client.post("/api/prefs", headers=headers, json={"key": "claude", "value": "x"})
        bad = client.post("/api/prefs", headers=headers, json={"key": "theme", "value": "rosa"})
        shown = client.get("/api/prefs", headers=headers).json()

    assert saved == [
        ("agent_mode", "manual"),
        ("speaker", "ellos"),
        ("closed_sources", ["tu"]),
        ("theme", "dark"),
    ]
    assert unknown.status_code == 404 and bad.status_code == 422
    assert shown["theme"] == "dark" and shown["speaker"] == "ellos"
