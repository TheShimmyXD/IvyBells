"""
Estructura por conceptos: qué carpeta puede importar a cuál.

Vigila lo que `check_structure.py` no ve durante la mudanza: la lista de puertas que aún
llaman a `services/` sin pasar por `app/`. Esa lista solo puede encoger: si un archivo se
limpia, la prueba pide sacarlo de la lista.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOORS = ("cli", "api", "ui_qt")
GUI_AND_HTTP = ("PySide6", "fastapi", "uvicorn", "starlette")

# Puertas que todavía crean o llaman servicios (FW.3, paso 4).
PENDING_SERVICES = {
    "entrypoints/ui_qt/workers/worker_context.py",
}


def _modules(path: Path) -> set[str]:
    """Primeros nombres de cada import absoluto del archivo (`from a.b import c` -> `a.b`)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def _files(folder: str) -> list[Path]:
    return sorted((ROOT / folder).rglob("*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _imports_any(modules: set[str], roots: tuple[str, ...]) -> bool:
    return any(name == root or name.startswith(root + ".") for name in modules for root in roots)


def test_domain_is_pure():
    bad = [
        _rel(path)
        for path in _files("domain")
        if _imports_any(_modules(path), ("services", "app", "entrypoints", *GUI_AND_HTTP))
    ]
    assert bad == []


def test_app_knows_no_door_nor_gui():
    bad = [
        _rel(path)
        for path in _files("app")
        if _imports_any(_modules(path), ("entrypoints", *GUI_AND_HTTP))
    ]
    assert bad == []


def test_services_know_no_app_nor_door():
    bad = [
        _rel(path)
        for path in _files("services")
        if _imports_any(_modules(path), ("app", "entrypoints", *GUI_AND_HTTP))
    ]
    assert bad == []


def test_no_door_imports_another_door():
    bad = []
    for door in DOORS:
        others = tuple(f"entrypoints.{other}" for other in DOORS if other != door)
        bad += [
            _rel(path)
            for path in _files(f"entrypoints/{door}")
            if _imports_any(_modules(path), others)
        ]
    assert bad == []


def test_doors_reach_services_only_from_the_pending_list():
    calling = {
        _rel(path) for path in _files("entrypoints") if _imports_any(_modules(path), ("services",))
    }
    assert calling - PENDING_SERVICES == set(), "Nueva puerta que llama a services/: use app/"
    assert PENDING_SERVICES - calling == set(), "Ya no llama a services/: sáquela de la lista"
