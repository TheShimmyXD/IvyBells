"""Copia en ``vendor/jacck_common`` lo que IvyBells usa de ``../jacck_common``.

``jacck_common`` es la librería propia del autor y vive solo en su máquina: no se publica.
El proyecto lleva dentro la copia de lo que usa (la API local ``webapi`` y el crate
``jacck_tauri``), para instalarse en otra máquina sin ella. Se edita siempre en
``../jacck_common`` y se trae con::

    python3 vendor/sync_jacck_common.py          # copia lo que cambió
    python3 vendor/sync_jacck_common.py --check  # sale 1 si las copias difieren

``tests/test_vendor_sync.py`` hace el ``--check`` (se salta sin ``../jacck_common``).
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "jacck_common"
DEST = ROOT / "vendor" / "jacck_common"

logger = logging.getLogger(__name__)

# Lo que se copia, relativo a la raíz de jacck_common. El pyproject.toml de vendor es
# propio (solo el extra webapi, sin keyring) y no se sincroniza.
PATTERNS = (
    "jacck_common/__init__.py",
    "jacck_common/webapi/*.py",
    "rust/jacck_tauri/Cargo.toml",
    "rust/jacck_tauri/Cargo.lock",
    "rust/jacck_tauri/src/*.rs",
)


def managed_files(base: Path) -> set[str]:
    """Rutas relativas (con ``/``) de los archivos de ``base`` que cubre ``PATTERNS``."""
    found: set[str] = set()
    for pattern in PATTERNS:
        found.update(path.relative_to(base).as_posix() for path in base.glob(pattern))
    return found


def differences(source: Path, dest: Path) -> list[str]:
    """Lo que separa la copia del original: ``falta``, ``sobra`` o ``distinto``."""
    origin = managed_files(source)
    copy = managed_files(dest)
    lines = [f"falta: {name}" for name in sorted(origin - copy)]
    lines += [f"sobra: {name}" for name in sorted(copy - origin)]
    lines += [
        f"distinto: {name}"
        for name in sorted(origin & copy)
        if (source / name).read_bytes() != (dest / name).read_bytes()
    ]
    return lines


def sync(source: Path, dest: Path) -> list[str]:
    """Deja ``dest`` igual a ``source`` en lo que cubre ``PATTERNS``; devuelve lo hecho."""
    changes = differences(source, dest)
    for line in changes:
        kind, name = line.split(": ", 1)
        target = dest / name
        if kind == "sobra":
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="solo compara; sale 1 si difieren")
    parser.add_argument("--source", type=Path, default=SOURCE, help="carpeta de jacck_common")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.source.is_dir():
        logger.error("No existe %s: no hay de dónde sincronizar.", args.source)
        return 1
    if args.check:
        lines = differences(args.source, DEST)
        for line in lines:
            logger.info(line)
        logger.info("vendor/jacck_common al día." if not lines else f"{len(lines)} diferencias.")
        return 1 if lines else 0
    lines = sync(args.source, DEST)
    for line in lines:
        logger.info(line)
    logger.info("%d archivos actualizados en vendor/jacck_common.", len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
