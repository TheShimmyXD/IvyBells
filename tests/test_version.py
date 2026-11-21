"""La version del proyecto es una sola en todos los archivos que la declaran.

Al subir de version se cambian todos a la vez; si uno queda atras, esta prueba lo nombra.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _toml(relative: str) -> dict:
    return tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def declared_versions() -> dict[str, str]:
    """Cada lugar que declara la version, con la que declara."""
    lock = _json("web/package-lock.json")
    crates = _toml("desktop/src-tauri/Cargo.lock")["package"]
    (desktop,) = (crate for crate in crates if crate["name"] == "ivybells-desktop")
    return {
        "pyproject.toml": _toml("pyproject.toml")["project"]["version"],
        "web/package.json": _json("web/package.json")["version"],
        "web/package-lock.json": lock["version"],
        'web/package-lock.json (packages[""])': lock["packages"][""]["version"],
        "desktop/src-tauri/tauri.conf.json": _json("desktop/src-tauri/tauri.conf.json")["version"],
        "desktop/src-tauri/Cargo.toml": _toml("desktop/src-tauri/Cargo.toml")["package"]["version"],
        "desktop/src-tauri/Cargo.lock": desktop["version"],
    }


def test_version_is_the_same_everywhere():
    versions = declared_versions()
    expected = versions["pyproject.toml"]
    behind = {place: version for place, version in versions.items() if version != expected}
    assert not behind, f"pyproject.toml dice {expected}; no coinciden: {behind}"
