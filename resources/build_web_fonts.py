"""Letras e iconos livianos para la ventana: recorte y WOFF2 desde resources/.

Los originales (TTF de IBM Plex y la Phosphor completa) quedan en resources/fonts y
resources/icons; aqui se escriben en resources/web/ las versiones que carga web/:

- IBM Plex recortado a latin-1, puntuacion general, euro, flechas y signos comunes. La OFL
  reserva el nombre "Plex" para la fuente sin modificar, asi que el recorte se llama
  "IvyBells Sans" o "IvyBells Mono" (conserva el copyright y la licencia).
- Phosphor con solo los iconos de web/src/shared/phosphor.ts, y phosphor-ui.json con los
  codigos que quedaron en la fuente (la prueba de web/ los compara con phosphor.ts).

Tras agregar un icono a phosphor.ts:

    .venv/bin/python resources/build_web_fonts.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "resources" / "fonts"
ICONS = ROOT / "resources" / "icons"
OUTPUT = ROOT / "resources" / "web"
PHOSPHOR_TS = ROOT / "web" / "src" / "shared" / "phosphor.ts"
ICON_CODES_JSON = "phosphor-ui.json"

# Latin-1, OE y oe, acentos sueltos, puntuacion general (rayas, comillas, ...), euro, marca,
# flechas y signos que puede escribir el Agente (menos, aprox., distinto, menor o igual).
TEXT_UNICODES = [
    *range(0x20, 0x7F),
    *range(0xA0, 0x100),
    0x131,
    0x152,
    0x153,
    0x2C6,
    0x2DA,
    0x2DC,
    *range(0x2000, 0x2070),
    0x20AC,
    0x2122,
    *range(0x2190, 0x2196),
    0x2212,
    0x2248,
    0x2260,
    0x2264,
    0x2265,
]

# Origen en resources/fonts -> (nombre recortado, familia nueva).
TEXT_FONTS = {
    "IBMPlexSans-Regular.ttf": ("IvyBellsSans-Regular.woff2", "IvyBells Sans"),
    "IBMPlexSans-Medium.ttf": ("IvyBellsSans-Medium.woff2", "IvyBells Sans"),
    "IBMPlexMono-Regular.ttf": ("IvyBellsMono-Regular.woff2", "IvyBells Mono"),
}
ICON_SOURCE = "phosphor-regular.woff2"
ICON_OUTPUT = "phosphor-ui.woff2"

# Registros de la tabla name que llevan el nombre de la fuente: familia (1, 16, 21),
# estilo completo (3, 4), PostScript (6, sin espacios) y variaciones (25). Copyright (0),
# marca (7) y licencia (13, 14) quedan tal cual.
_NAME_IDS = {1, 3, 4, 6, 16, 18, 21, 25}
_OLD_FAMILIES = ("IBM Plex Sans", "IBM Plex Mono")

_ICON_CODE = re.compile(r"0x([0-9a-fA-F]+)")

log = logging.getLogger(__name__)


def icon_codes(phosphor_ts: Path) -> list[int]:
    """Los codigos de iconos de phosphor.ts, sin repetir y en orden."""
    return sorted({int(code, 16) for code in _ICON_CODE.findall(phosphor_ts.read_text())})


def rename_family(font: TTFont, family: str) -> None:
    """Cambia el nombre de la familia en la tabla name (OFL: nombre reservado)."""
    compact = family.replace(" ", "")
    for record in font["name"].names:
        if record.nameID not in _NAME_IDS:
            continue
        text = record.toUnicode()
        for old in _OLD_FAMILIES:
            text = text.replace(old, family).replace(old.replace(" ", ""), compact)
        record.string = text


def subset_font(source: Path, output: Path, unicodes: list[int], family: str = "") -> None:
    """Recorta la fuente a esos codigos y la guarda en WOFF2, con otra familia si se da."""
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    font = subset.load_font(str(source), options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    if family:
        rename_family(font, family)
    output.parent.mkdir(parents=True, exist_ok=True)
    subset.save_font(font, str(output), options)


def mapped_codes(path: Path) -> list[int]:
    """Los codigos que la fuente sabe dibujar (su cmap)."""
    with TTFont(path) as font:
        return sorted(font.getBestCmap())


def build(output: Path = OUTPUT) -> list[Path]:
    """Escribe en `output` las letras recortadas, la Phosphor de la web y su lista de codigos."""
    written = []
    for source, (name, family) in TEXT_FONTS.items():
        subset_font(FONTS / source, output / name, TEXT_UNICODES, family)
        written.append(output / name)
    subset_font(ICONS / ICON_SOURCE, output / ICON_OUTPUT, icon_codes(PHOSPHOR_TS))
    codes = [f"{code:x}" for code in mapped_codes(output / ICON_OUTPUT)]
    (output / ICON_CODES_JSON).write_text(json.dumps(codes, indent=2) + "\n")
    written += [output / ICON_OUTPUT, output / ICON_CODES_JSON]
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # fontTools avisa de tablas que descarta (meta, FFTM): no afectan al dibujo.
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    for path in build():
        log.info("%s: %d bytes", path.relative_to(ROOT), path.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
