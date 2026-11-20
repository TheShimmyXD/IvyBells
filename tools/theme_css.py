"""Genera las variables CSS de la interfaz web desde el tema de Qt.

``entrypoints/ui_qt/theme.py`` sigue siendo la unica fuente de colores; las medidas de la
barra salen de ``_00_ui_sidebar.py`` y los radios de ``theme_qss.py``. Este script los lee y
escribe ``web/src/shared/theme/tokens.css``. Tras cambiar un token:

    .venv/bin/python tools/theme_css.py

``tests/test_theme_css.py`` falla si el CSS quedo desfasado del tema.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoints.ui_qt._00_ui_sidebar import (  # noqa: E402
    BUTTON_HEIGHT,
    COLLAPSED_WIDTH,
    EXPANDED_WIDTH,
    ICON_SIZE,
    LOGO_SIZE,
)
from entrypoints.ui_qt.theme import DARK, LIGHT, SPACING_SCALE, WIDE, ColorTokens  # noqa: E402
from entrypoints.ui_qt.theme_qss import (  # noqa: E402
    FLOATING_RADIUS,
    PANEL_RADIUS,
    PILL_RADIUS,
    RADIUS,
)

OUTPUT = ROOT / "web" / "src" / "shared" / "theme" / "tokens.css"
HEADER = "/* Generado por tools/theme_css.py desde entrypoints/ui_qt/theme.py: no editar a mano. */"
SANS = '"IBM Plex Sans", system-ui, sans-serif'
MONO = '"IBM Plex Mono", ui-monospace, monospace'


def css_name(field_name: str) -> str:
    return "--color-" + field_name.replace("_", "-")


def css_color(value: str) -> str:
    """``#AARRGGBB`` (la forma de Qt, solo la sombra) pasa a ``#RRGGBBAA`` de CSS.

    En minusculas, como lo deja Prettier: el archivo generado pasa su revision tal cual.
    """
    if len(value) == 9:
        value = "#" + value[3:] + value[1:3]
    return value.lower()


def color_lines(tokens: ColorTokens) -> list[str]:
    return [
        f"  {css_name(item.name)}: {css_color(getattr(tokens, item.name))};"
        for item in fields(ColorTokens)
    ]


def shape_lines() -> list[str]:
    lines = [
        f"  --radius: {RADIUS}px;",
        f"  --radius-pill: {PILL_RADIUS}px;",
        f"  --radius-panel: {PANEL_RADIUS}px;",
        f"  --radius-floating: {FLOATING_RADIUS}px;",
        f"  --sidebar-collapsed: {COLLAPSED_WIDTH}px;",
        f"  --sidebar-expanded: {EXPANDED_WIDTH}px;",
        f"  --sidebar-button: {BUTTON_HEIGHT}px;",
        f"  --sidebar-icon: {ICON_SIZE}px;",
        f"  --sidebar-logo: {LOGO_SIZE}px;",
    ]
    lines += [f"  --space-{index}: {value}px;" for index, value in enumerate(SPACING_SCALE, 1)]
    lines += [
        f"  --margin: {WIDE.margin}px;",
        f"  --spacing: {WIDE.spacing}px;",
        f"  --font-sans: {SANS};",
        f"  --font-mono: {MONO};",
    ]
    return lines


def build_css() -> str:
    """El CSS completo: el tema claro en ``:root`` y el oscuro con ``data-theme``."""
    parts = [
        HEADER,
        ":root {",
        "  color-scheme: light;",
        *color_lines(LIGHT),
        *shape_lines(),
        "}",
        "",
        ':root[data-theme="dark"] {',
        "  color-scheme: dark;",
        *color_lines(DARK),
        "}",
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_css(), encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger(__name__).info("Escrito %s", OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
