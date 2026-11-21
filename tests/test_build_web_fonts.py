"""Pruebas del recorte de letras e iconos de la ventana (resources/build_web_fonts.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "build_web_fonts", ROOT / "resources" / "build_web_fonts.py"
)
fonts = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fonts)


def test_icon_codes_reads_hex_codes_once_and_sorted(tmp_path):
    ts = tmp_path / "phosphor.ts"
    ts.write_text('export const P = {\n  b: 0xe02a,\n  a: 0xE001,\n  "c-d": 0xe02a,\n};\n')

    assert fonts.icon_codes(ts) == [0xE001, 0xE02A]


def test_icon_subset_has_exactly_the_requested_icons(tmp_path):
    codes = fonts.icon_codes(fonts.PHOSPHOR_TS)
    output = tmp_path / "icons.woff2"

    fonts.subset_font(fonts.ICONS / fonts.ICON_SOURCE, output, codes)

    assert fonts.mapped_codes(output) == codes
    assert output.stat().st_size < 10_000


def test_text_subset_keeps_spanish_and_drops_the_reserved_name(tmp_path):
    output = tmp_path / "sans.woff2"

    fonts.subset_font(
        fonts.FONTS / "IBMPlexSans-Regular.ttf", output, fonts.TEXT_UNICODES, "IvyBells Sans"
    )

    mapped = set(fonts.mapped_codes(output))
    assert {ord(ch) for ch in "áéíóúüñÁÉÍÓÚÜÑ¿¡«»…—–€"} <= mapped
    with TTFont(output) as font:
        names = {r.nameID: r.toUnicode() for r in font["name"].names if r.platformID == 3}
    assert names[1] == "IvyBells Sans"
    assert names[6].startswith("IvyBellsSans")
    assert not any("Plex" in names[i] for i in fonts._NAME_IDS if i in names)
    assert "IBM" in names[0]


def test_committed_icon_list_covers_phosphor_ts():
    listed = json.loads((fonts.OUTPUT / fonts.ICON_CODES_JSON).read_text())

    assert {int(code, 16) for code in listed} == set(fonts.icon_codes(fonts.PHOSPHOR_TS))
    assert fonts.mapped_codes(fonts.OUTPUT / fonts.ICON_OUTPUT) == fonts.icon_codes(
        fonts.PHOSPHOR_TS
    )
