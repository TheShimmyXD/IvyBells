"""El CSS de la web sale del tema de Qt y no se desfasa."""

from __future__ import annotations

from tools.theme_css import OUTPUT, build_css, css_color


def test_qt_shadow_becomes_css_rgba() -> None:
    assert css_color("#50000000") == "#00000050"
    assert css_color("#1F5266") == "#1f5266"


def test_both_themes_are_written() -> None:
    css = build_css()
    assert "--color-brand: #1f5266;" in css
    assert ':root[data-theme="dark"]' in css
    assert "--color-brand: #7dbcd0;" in css
    assert "--sidebar-collapsed: 52px;" in css


def test_tokens_css_matches_the_qt_theme() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == build_css(), (
        "tokens.css desfasado: corre .venv/bin/python tools/theme_css.py"
    )
