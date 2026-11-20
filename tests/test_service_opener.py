"""Pruebas de `services/service_opener.py` con un lanzador falso (no abre nada)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.service_opener import open_command, open_path


def test_open_command_uses_xdg_open_on_linux() -> None:
    assert open_command(Path("/x/y"), "linux") == ["xdg-open", "/x/y"]


def test_open_command_uses_open_on_mac() -> None:
    assert open_command(Path("/x/y"), "darwin") == ["open", "/x/y"]


def test_open_path_launches_the_command(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    open_path(tmp_path, launcher=lambda command: calls.append(list(command)), platform="linux")
    assert calls == [["xdg-open", str(tmp_path)]]


def test_open_path_refuses_a_missing_path(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    with pytest.raises(FileNotFoundError):
        open_path(tmp_path / "no", launcher=lambda command: calls.append(list(command)))
    assert calls == []
