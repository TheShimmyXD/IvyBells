"""API local minima de IvyBells: token y salud, sin red ni GPU."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="extra web: ./install.sh (jacck_common)")

from fastapi.testclient import TestClient
from jacck_common.webapi.security import new_token

from app.live import LiveListening
from entrypoints.api.run import NAMES, app_version, create_api


def test_names_are_the_ones_the_window_uses() -> None:
    # Los mismos que arma desktop/src-tauri/src/main.rs con el prefijo IVYBELLS.
    assert NAMES.token_env == "IVYBELLS_API_TOKEN"
    assert NAMES.port_line(1) == "IVYBELLS_API_PORT=1"


def test_health_needs_the_token_and_gives_the_version(tmp_path) -> None:
    token = new_token()
    listening = LiveListening(lambda *_: None, tmp_path)
    with TestClient(create_api(token, listening), base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").status_code == 401
        response = client.get("/api/health", headers={"Authorization": f"Bearer {token}"})
    assert response.json() == {"ok": True, "version": app_version()}
    assert token not in response.text
