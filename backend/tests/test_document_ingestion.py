from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.document_ingestion import (
    DocumentExtractionError,
    DocumentPage,
    EmptyPdfTextError,
    UnsupportedDocumentFormatError,
    extract_document,
)

def test_extracts_and_normalizes_markdown(tmp_path: Path):
    source = tmp_path / "guide.md"
    source.write_bytes("# Título  \r\n\r\nContenido.   \r\n".encode("utf-8"))

    document = extract_document(source)

    assert document.text == "# Título\n\nContenido."
    assert document.metadata.filename == "guide.md"
    assert document.metadata.format == "md"
    assert document.metadata.character_count == len(document.text)
    assert document.metadata.page_count is None
    assert document.pages == ()


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
    assert document.pages == (
        DocumentPage(page_number=1, text="Page one"),
        DocumentPage(page_number=2, text="Page two"),
    )


def test_extracts_pdf_image_with_origin_position(tmp_path: Path):
    source = tmp_path / "diagram.pdf"
    image = Image.new("RGB", (20, 20), "white")
    image.save(source, format="PDF")

    reader = PdfReader(str(source))
    page = reader.pages[0]
    writer = PdfWriter()
    page.merge_page(_pdf_page("Diagram example"))
    writer.add_page(page)
    with source.open("wb") as file:
        writer.write(file)

    document = extract_document(source)

    assert document.text == "Diagram example"
    assert len(document.images) == 1
    extracted_image = document.images[0]
    assert extracted_image.page_number == 1
    assert extracted_image.image_index == 1
    assert extracted_image.data
    assert extracted_image.mime_type.startswith("image/")
    assert (extracted_image.width, extracted_image.height) == (20, 20)


def test_pdf_image_extraction_failure_preserves_text(monkeypatch, tmp_path: Path):
    source = tmp_path / "image-error.pdf"
    source.write_bytes(b"fake-pdf")

    class PageWithBrokenImages:
        def extract_text(self):
            return "Texto técnico disponible"

        @property
        def images(self):
            raise RuntimeError("unsupported image filter")

    monkeypatch.setattr(
        "app.services.document_ingestion.PdfReader",
        lambda *_: SimpleNamespace(pages=[PageWithBrokenImages()]),
    )

    document = extract_document(source)

    assert document.text == "Texto técnico disponible"
    assert document.images == ()


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

def test_rejects_latin1_text_with_controlled_error(tmp_path: Path):
    source = tmp_path / "texto_latin1.txt"
    source.write_bytes(
        "Información técnica en español".encode("latin-1")
    )

    with pytest.raises(
        DocumentExtractionError,
        match="La codificación debe ser UTF-8",
    ):
        extract_document(source)

def test_rejects_empty_text_file(tmp_path: Path):
    source = tmp_path / "archivo_vacio.txt"
    source.write_bytes(b"")

    with pytest.raises(
        DocumentExtractionError,
        match="está vacío o no contiene texto válido",
    ):
        extract_document(source)


def test_rejects_whitespace_only_markdown(tmp_path: Path):
    source = tmp_path / "archivo_vacio.md"
    source.write_text("   \n  \t  \n", encoding="utf-8")

    with pytest.raises(
        DocumentExtractionError,
        match="está vacío o no contiene texto válido",
    ):
        extract_document(source)
