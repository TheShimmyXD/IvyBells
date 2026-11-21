"""Copia de jacck_common en vendor/: el script de sincronización y la copia real."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "sync_jacck_common", ROOT / "vendor" / "sync_jacck_common.py"
)
sync_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync_module)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake_common(base: Path) -> Path:
    _write(base / "jacck_common" / "__init__.py", "__version__ = '9.9.9'\n")
    _write(base / "jacck_common" / "webapi" / "server.py", "SERVER = 1\n")
    _write(base / "jacck_common" / "credentials.py", "no se copia\n")
    _write(base / "jacck_common" / "webapi" / "__pycache__" / "server.cpython-313.pyc", "x")
    _write(base / "rust" / "jacck_tauri" / "Cargo.toml", "[package]\n")
    _write(base / "rust" / "jacck_tauri" / "src" / "lib.rs", "// lib\n")
    _write(base / "rust" / "target" / "release" / "basura", "no se copia\n")
    return base


def test_sync_copies_only_what_ivybells_uses(tmp_path):
    source = _fake_common(tmp_path / "common")
    dest = tmp_path / "vendor"

    changes = sync_module.sync(source, dest)

    assert len(changes) == 4
    assert sync_module.differences(source, dest) == []
    assert not (dest / "jacck_common" / "credentials.py").exists()
    assert not (dest / "rust" / "target").exists()
    assert not (dest / "jacck_common" / "webapi" / "__pycache__").exists()


def test_check_reports_changed_missing_and_stale_files(tmp_path):
    source = _fake_common(tmp_path / "common")
    dest = tmp_path / "vendor"
    sync_module.sync(source, dest)
    _write(source / "jacck_common" / "webapi" / "server.py", "SERVER = 2\n")
    _write(source / "jacck_common" / "webapi" / "jobs.py", "JOBS = 1\n")
    _write(dest / "rust" / "jacck_tauri" / "src" / "viejo.rs", "// ya no esta\n")

    assert sync_module.differences(source, dest) == [
        "falta: jacck_common/webapi/jobs.py",
        "sobra: rust/jacck_tauri/src/viejo.rs",
        "distinto: jacck_common/webapi/server.py",
    ]
    sync_module.sync(source, dest)
    assert sync_module.differences(source, dest) == []
    assert not (dest / "rust" / "jacck_tauri" / "src" / "viejo.rs").exists()


@pytest.mark.skipif(
    not sync_module.SOURCE.is_dir(), reason="sin ../jacck_common (otra máquina o CI)"
)
def test_vendor_matches_jacck_common():
    lines = sync_module.differences(sync_module.SOURCE, sync_module.DEST)
    assert lines == [], "corre: python3 vendor/sync_jacck_common.py\n" + "\n".join(lines)


def test_vendor_has_what_ivybells_imports_and_its_version():
    dest = sync_module.DEST
    for module in ("events", "names", "security", "serve", "server"):
        assert (dest / "jacck_common" / "webapi" / f"{module}.py").is_file()
    assert (dest / "rust" / "jacck_tauri" / "src" / "lib.rs").is_file()
    init = (dest / "jacck_common" / "__init__.py").read_text(encoding="utf-8")
    with (dest / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    assert f'__version__ = "{version}"' in init


def test_desktop_builds_the_vendored_crate():
    with (ROOT / "desktop" / "src-tauri" / "Cargo.toml").open("rb") as handle:
        path = tomllib.load(handle)["dependencies"]["jacck_tauri"]["path"]
    crate = (ROOT / "desktop" / "src-tauri" / path).resolve()
    assert crate == (sync_module.DEST / "rust" / "jacck_tauri").resolve()
