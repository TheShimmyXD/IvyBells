"""Acceso del menú: icono copiado y .desktop con rutas absolutas y el nombre de la ventana."""

from __future__ import annotations

from pathlib import Path

from services.service_launcher import data_home, desktop_entry, install_launcher


def _fields(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def test_install_writes_icon_and_entry_under_data_home(tmp_path):
    root = tmp_path / "IvyBells"
    root.mkdir()
    logo = root / "logo.png"
    logo.write_bytes(b"\x89PNG prueba")
    entry = install_launcher(root, root / ".venv/bin/python", logo, home=tmp_path / "share")

    icon = tmp_path / "share/icons/hicolor/256x256/apps/IvyBells.png"
    assert entry == tmp_path / "share/applications/IvyBells.desktop"
    assert icon.read_bytes() == b"\x89PNG prueba"
    fields = _fields(entry.read_text(encoding="utf-8"))
    assert fields["Exec"] == f"{root}/.venv/bin/python {root}/main.py"
    assert fields["Path"] == str(root)
    assert fields["Icon"] == str(icon)
    assert fields["StartupWMClass"] == "IvyBells"
    assert entry.stat().st_mode & 0o111


def test_exec_quotes_paths_with_spaces():
    root = Path("/opt/mis apps/IvyBells")
    fields = _fields(desktop_entry(root, root / ".venv/bin/python", Path("/i.png")))
    assert fields["Exec"] == (
        '"/opt/mis apps/IvyBells/.venv/bin/python" "/opt/mis apps/IvyBells/main.py"'
    )


def test_data_home_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert data_home() == tmp_path
    monkeypatch.setenv("XDG_DATA_HOME", "")
    assert data_home() == Path.home() / ".local" / "share"
