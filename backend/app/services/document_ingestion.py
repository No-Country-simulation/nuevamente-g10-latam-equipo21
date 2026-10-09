"""Extracción y normalización de documentos soportados."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final
import unicodedata

from pypdf import PdfReader


SUPPORTED_FORMATS: Final = {"pdf", "md", "txt"}


class DocumentExtractionError(Exception):
    """Error base para fallos en la ingesta de documentos."""


class UnsupportedDocumentFormatError(DocumentExtractionError):
    """Se genera cuando no se admite una extensión de documento.."""


class EmptyPdfTextError(DocumentExtractionError):
    """Se activa cuando un PDF no tiene una capa de texto extraíble.."""


@dataclass(frozen=True)
class DocumentMetadata:
    """Metadatos básicos recopilados de un documento ingerido."""

    filename: str
    format: str
    character_count: int
    page_count: int | None = None


@dataclass(frozen=True)
class ExtractedImage:
    """Imagen extraída de un PDF con su posición de origen."""

    data: bytes
    name: str
    page_number: int
    image_index: int
    mime_type: str


@dataclass(frozen=True)
class DocumentPage:
    """Texto normalizado de una página y su número (1-indexado)."""

    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    """Texto normalizado del documento, sus páginas y metadatos de origen.."""

    text: str
    metadata: DocumentMetadata

    pages: tuple[DocumentPage, ...] = ()
    images: tuple[ExtractedImage, ...] = ()


def extract_document(file_path: str | Path) -> ExtractedDocument:
    """Extraer texto plano normalizado de un archivo PDF, Markdown o de texto.."""
    path = Path(file_path)
    document_format = path.suffix.lower().lstrip(".")

    if document_format not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise UnsupportedDocumentFormatError(
            f"Formato no soportado: '.{document_format or path.name}'. "
            f"Formatos permitidos: {supported}."
        )

    if document_format == "pdf":
        text, raw_pages, images = _extract_pdf(path)
        page_count = len(raw_pages)
        pages = _build_pages(raw_pages)
    else:
        text = _read_text(path)
        page_count = None
        pages = ()
        images = ()

    normalized_text = _normalize_text(text)
    metadata = DocumentMetadata(
        filename=path.name,
        format=document_format,
        character_count=len(normalized_text),
        page_count=page_count,
    )

    return ExtractedDocument(
        text=normalized_text,
        metadata=metadata,
        pages=pages,
        images=images,
    )

def _extract_pdf(path: Path) -> tuple[str, list[str], tuple[ExtractedImage, ...]]:
    """Extrae texto por página e imágenes de un documento PDF."""
    reader = PdfReader(str(path))
    
    pages_text: list[str] = []
    extracted_images: list[ExtractedImage] = []

    for page_number, page in enumerate(reader.pages, start=1):
        pages_text.append(page.extract_text() or "")

        for image_index, image_file in enumerate(page.images, start=1):
            suffix = Path(image_file.name).suffix.lower()

            mime_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".tif": "image/tiff",
                ".tiff": "image/tiff",
            }.get(suffix, "application/octet-stream")

            extracted_images.append(
                ExtractedImage(
                    data=image_file.data,
                    name=image_file.name,
                    page_number=page_number,
                    image_index=image_index,
                    mime_type=mime_type,
                )
            )

    text = "\n\n".join(pages_text)

    if not text.strip():
        raise EmptyPdfTextError(
            f"El PDF '{path.name}' no contiene texto extraíble; OCR está fuera de alcance."
        )
    return text, pages_text, tuple(extracted_images)


def _build_pages(raw_pages: list[str]) -> tuple[DocumentPage, ...]:
    """Normaliza cada página y conserva su número real (1-indexado), descartando las vacías."""
    paginas = []

    for index, raw in enumerate(raw_pages, start=1):
        normalized = _normalize_text(raw)

        if normalized:
            paginas.append(
                DocumentPage(
                    page_number=index,
                    text=normalized,
                )
            )

    return tuple(paginas)


def _read_text(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return file.read()


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()