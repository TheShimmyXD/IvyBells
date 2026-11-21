"""Ventana de Tauri: ruta del binario desde los archivos de desktop/ y apertura con execve."""

from __future__ import annotations

from pathlib import Path

from services.service_desktop import (
    ROOT_ENV,
    binary_name,
    build_binary,
    installed_binary,
    open_window,
    release_binary,
)

ROOT = Path(__file__).resolve().parents[1]
SRC_TAURI = ROOT / "desktop" / "src-tauri"


def _src_tauri(tmp_path: Path, target_dir: str | None) -> Path:
    src = tmp_path / "app" / "desktop" / "src-tauri"
    src.mkdir(parents=True)
    (src / "Cargo.toml").write_text('[package]\nname = "demo-desktop"\n', encoding="utf-8")
    if target_dir is not None:
        (src / ".cargo").mkdir()
        (src / ".cargo" / "config.toml").write_text(
            f'[build]\ntarget-dir = "{target_dir}"\n', encoding="utf-8"
        )
    return src


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_build_binary_follows_the_shared_target_dir(tmp_path):
    src = _src_tauri(tmp_path, "../../../comun/rust/target")
    expected = tmp_path / "comun" / "rust" / "target" / "release" / "demo-desktop"
    assert build_binary(src) == expected
    assert release_binary(src) == expected


def test_build_binary_without_cargo_config_uses_its_own_target(tmp_path):
    src = _src_tauri(tmp_path, None)
    assert build_binary(src) == src / "target" / "release" / "demo-desktop"


def test_release_binary_uses_the_installed_copy_when_target_was_removed(tmp_path):
    # Otra máquina: install.sh copió el binario a desktop/bin y borró target/.
    src = _src_tauri(tmp_path, None)
    copy = _touch(installed_binary(src))
    assert copy == src.parent / "bin" / "demo-desktop"
    assert release_binary(src) == copy


def test_release_binary_prefers_a_fresh_build_over_the_installed_copy(tmp_path):
    # Recompilar tras cambiar web/ deja target/ de nuevo: manda lo compilado.
    src = _src_tauri(tmp_path, None)
    _touch(installed_binary(src))
    built = _touch(build_binary(src))
    assert release_binary(src) == built


def test_release_binary_without_any_binary_names_the_build_path(tmp_path):
    src = _src_tauri(tmp_path, None)
    assert release_binary(src) == build_binary(src)


def test_project_binary_follows_the_local_cargo_config():
    # .cargo/config.toml es local: lo escribe install.sh si existe ../jacck_common.
    binary = build_binary(SRC_TAURI)
    assert binary_name(SRC_TAURI) == "ivybells-desktop"
    if (SRC_TAURI / ".cargo" / "config.toml").is_file():
        target = ROOT.parent / "jacck_common" / "rust" / "target"
    else:
        target = SRC_TAURI / "target"
    assert binary == target / "release" / binary.name


def test_missing_binary_returns_one_without_exec(tmp_path, caplog):
    calls = []
    code = open_window(tmp_path / "nada", tmp_path, exec_fn=lambda *a: calls.append(a))
    assert code == 1
    assert calls == []
    assert "install.sh" in caplog.text


def test_open_window_execs_the_binary_with_the_root(tmp_path):
    binary = tmp_path / "demo-desktop"
    binary.write_bytes(b"")
    calls = []
    code = open_window(
        binary, tmp_path / "raiz", exec_fn=lambda *a: calls.append(a), env={"HOME": "/h"}
    )
    assert code == 0
    path, argv, env = calls[0]
    assert path == binary
    assert argv == [str(binary)]
    assert env == {"HOME": "/h", ROOT_ENV: str(tmp_path / "raiz")}
