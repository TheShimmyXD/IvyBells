from __future__ import annotations

import os

import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from core.agent_context import REASON_MEDIA, REASON_SECRET
from services.service_context import collect, read_context, write_context

_HELVETICA = DictionaryObject(
    {
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }
)


def _pdf(path, pages, password=None):
    """Un PDF real con una línea de texto por página (sin acentos: Helvetica estándar)."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(612, 792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): _HELVETICA})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page.replace_contents(stream)
    if password:
        writer.encrypt(password, algorithm="RC4-128")
    writer.write(path)


@pytest.fixture
def company(tmp_path):
    root = tmp_path / "empresa"
    (root / "sub").mkdir(parents=True)
    (root / "servicios.md").write_text("Plan básico", encoding="utf-8")
    (root / "sub" / "precios.csv").write_text("plan,precio\n", encoding="utf-8")
    for folder in (".git", ".venv", "node_modules"):
        (root / folder).mkdir()
        (root / folder / "dentro.md").write_text("no", encoding="utf-8")
    (root / ".env").write_text("CLAVE=1", encoding="utf-8")
    (root / "latin1.txt").write_bytes("año".encode("latin-1"))
    (root / "nulos.txt").write_bytes(b"a\0b")
    audio = root / "llamada.wav"
    audio.write_bytes(b"RIFF")
    audio.chmod(0)  # si se abriera, el motivo sería otro
    yield root
    audio.chmod(0o644)


def _reasons(omitted):
    return {os.path.basename(item.path): item.reason for item in omitted}


def test_filters(company):
    files, omitted = collect([str(company)])
    names = [os.path.basename(item.path) for item in files]
    assert names == ["servicios.md", "precios.csv"]
    reasons = _reasons(omitted)
    assert reasons["llamada.wav"] == REASON_MEDIA
    assert reasons[".env"] == REASON_SECRET
    assert reasons["latin1.txt"] == "no es UTF-8"
    assert reasons["nulos.txt"] == "binario"
    assert "dentro.md" not in reasons


def test_missing_path_and_duplicates(company, tmp_path):
    single = str(company / "servicios.md")
    files, omitted = collect([single, str(company), str(tmp_path / "no_hay")])
    assert [item.path for item in files].count(single) == 1
    assert _reasons(omitted)["no_hay"] == "no existe"


def test_file_cap(company, monkeypatch):
    import services.service_context as module

    monkeypatch.setattr(module, "MAX_FILES", 1)
    files, omitted = collect([str(company)])
    assert len(files) == 1
    assert "tope de 1 archivos" in _reasons(omitted)["precios.csv"]


def test_long_file_is_clipped(tmp_path):
    long = tmp_path / "largo.txt"
    long.write_text("á" * 30_000, encoding="utf-8")
    files, _ = collect([str(long)])
    assert files[0].truncated and len(files[0].text) == 20_000


def test_photo_does_not_change_if_files_do_not(company, tmp_path):
    target = tmp_path / "contexto" / "contexto.md"
    first = write_context([str(company)], target)
    assert first.changed and first.files == 2
    assert not write_context([str(company)], target).changed
    (company / "servicios.md").write_text("Plan premium", encoding="utf-8")
    assert write_context([str(company)], target).changed
    assert "Plan premium" in read_context(target)


def test_no_paths_empty_photo(tmp_path):
    target = tmp_path / "contexto.md"
    write_context([], target)
    assert read_context(target) == ""
    assert read_context(tmp_path / "no_hay.md") == ""


def test_pdf_text(tmp_path):
    _pdf(tmp_path / "catalogo.pdf", ["Plan basico 10 USD", "Plan premium 25 USD"])
    files, omitted = collect([str(tmp_path)])
    assert not omitted
    assert "Plan basico 10 USD" in files[0].text and "Plan premium 25 USD" in files[0].text


def test_docx_text_keeps_order_and_tables(tmp_path):
    document = Document()
    document.add_paragraph("Contrato de servicio")
    table = document.add_table(rows=2, cols=2)
    for row, values in zip(table.rows, [("plan", "precio"), ("básico", "10")], strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    document.add_paragraph("Vigencia: un año")
    document.save(tmp_path / "contrato.docx")
    files, _ = collect([str(tmp_path)])
    assert files[0].text == "Contrato de servicio\nplan | precio\nbásico | 10\nVigencia: un año"


def test_documents_that_give_no_text(tmp_path):
    _pdf(tmp_path / "cifrado.pdf", ["secreto"], password="clave")
    _pdf(tmp_path / "escaneado.pdf", [""])
    (tmp_path / "roto.pdf").write_bytes(b"%PDF-1.4 basura")
    (tmp_path / "roto.docx").write_bytes(b"PK no es zip")
    files, omitted = collect([str(tmp_path)])
    assert not files
    reasons = _reasons(omitted)
    assert reasons["cifrado.pdf"] == "PDF con contraseña"
    assert reasons["escaneado.pdf"] == "sin texto (¿escaneado?)"
    assert reasons["roto.pdf"] == reasons["roto.docx"] == "documento dañado o no soportado"


def test_big_document_is_not_opened(tmp_path, monkeypatch):
    import services.service_context as module

    monkeypatch.setattr(module, "MAX_DOCUMENT_BYTES", 10)
    _pdf(tmp_path / "grande.pdf", ["texto"])
    _, omitted = collect([str(tmp_path)])
    assert _reasons(omitted)["grande.pdf"].startswith("más de")


def test_long_pdf_stops_at_the_cap(tmp_path):
    _pdf(tmp_path / "manual.pdf", ["x" * 90] * 400)
    files, _ = collect([str(tmp_path)])
    assert files[0].truncated and len(files[0].text) == 20_000
