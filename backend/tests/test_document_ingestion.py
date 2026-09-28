from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.document_ingestion import (
    EmptyPdfTextError,
    UnsupportedDocumentFormatError,
    extract_document,
)


def test_extracts_and_normalizes_markdown(tmp_path: Path):
    source = tmp_path / "guide.md"
    source.write_text("# Título  \r\n\r\nContenido.   \r\n", encoding="utf-8")

    document = extract_document(source)

    assert document.text == "# Título\n\nContenido."
    assert document.metadata.filename == "guide.md"
    assert document.metadata.format == "md"
    assert document.metadata.character_count == len(document.text)
    assert document.metadata.page_count is None


def test_extracts_text_file(tmp_path: Path):
    source = tmp_path / "notes.txt"
    source.write_text("Primera línea\nSegunda línea", encoding="utf-8")

    document = extract_document(source)

    assert document.text == "Primera línea\nSegunda línea"
    assert document.metadata.format == "txt"


def test_rejects_unsupported_format(tmp_path: Path):
    source = tmp_path / "image.docx"
    source.write_bytes(b"not supported")

    with pytest.raises(UnsupportedDocumentFormatError, match="Formatos permitidos"):
        extract_document(source)


def test_rejects_scanned_pdf_without_text_layer(tmp_path: Path):
    source = tmp_path / "scanned.pdf"
    source.write_bytes(_pdf_bytes(""))

    with pytest.raises(EmptyPdfTextError, match="no contiene texto extraíble"):
        extract_document(source)


def test_extracts_pdf_pages_in_reading_order(tmp_path: Path):
    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_page(_pdf_page("Page one"))
    writer.add_page(_pdf_page("Page two"))
    with source.open("wb") as file:
        writer.write(file)

    document = extract_document(source)

    assert document.text == "Page one\n\nPage two"
    assert document.metadata.page_count == 2


def _pdf_bytes(content: str) -> bytes:
    writer = PdfWriter()
    writer.add_page(_pdf_page(content))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _pdf_page(content: str):
    page = PdfWriter().add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({content}) Tj ET".encode())
    page[NameObject("/Contents")] = stream
    return page