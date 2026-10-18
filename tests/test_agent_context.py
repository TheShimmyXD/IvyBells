from __future__ import annotations

import pytest

from core.agent_context import (
    MAX_FILE_CHARS,
    REASON_DOCUMENT,
    REASON_HIDDEN,
    REASON_MEDIA,
    REASON_MODEL,
    REASON_SECRET,
    REASON_TYPE,
    ContextFile,
    Omitted,
    build_context,
    clean_paths,
    clip,
    omit_reason,
    skip_dir,
)


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("servicios.md", ""),
        ("PRECIOS.CSV", ""),
        ("main.py", ""),
        (".env", REASON_SECRET),
        (".env.local", REASON_SECRET),
        ("servidor.pem", REASON_SECRET),
        (".notas.md", REASON_HIDDEN),
        ("llamada.wav", REASON_MEDIA),
        ("demo.mp4", REASON_MEDIA),
        ("model.safetensors", REASON_MODEL),
        ("catalogo.pdf", REASON_DOCUMENT),
        ("contrato.docx", REASON_DOCUMENT),
        ("logo.png", REASON_TYPE),
        ("sin_extension", REASON_TYPE),
    ],
)
def test_omit_reason(name, reason):
    assert omit_reason(name) == reason


@pytest.mark.parametrize("name", [".git", ".venv", "node_modules", "__pycache__", ".cache"])
def test_skip_dir(name):
    assert skip_dir(name)
    assert not skip_dir("documentos")


def test_clip():
    assert clip("abc", 5) == ("abc", False)
    assert clip("x" * (MAX_FILE_CHARS + 1)) == ("x" * MAX_FILE_CHARS, True)


def test_build_context_is_stable_and_sorted():
    files = [ContextFile("/b/zeta.md", "z"), ContextFile("/a/alfa.md", "a", truncated=True)]
    omitted = [Omitted("/c/x.pdf", REASON_DOCUMENT)]
    text = build_context(files, omitted)
    assert text == build_context(list(reversed(files)), omitted)
    assert text.index("## /a/alfa.md") < text.index("## /b/zeta.md") < text.index("## Omitidos")
    assert f"Recortado a {MAX_FILE_CHARS}" in text
    assert "- /c/x.pdf: PDF u Office" in text


def test_fence_is_longer_than_backticks_inside():
    text = build_context([ContextFile("/a.md", "uno\n````\ndos")], [])
    assert "\n`````\nuno" in text


def test_empty_context_says_so():
    assert "- (ninguno)" in build_context([], [])


def test_clean_paths():
    assert clean_paths(["  /a ", "", "/b", "/a", "   "]) == ["/a", "/b"]
