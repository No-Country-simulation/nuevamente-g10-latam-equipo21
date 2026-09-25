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
class ExtractedDocument:
    """Texto normalizado del documento y sus metadatos de origen.."""

    text: str
    metadata: DocumentMetadata


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
        text, page_count = _extract_pdf(path)
    else:
        text = _read_text(path)
        page_count = None

    normalized_text = _normalize_text(text)
    metadata = DocumentMetadata(
        filename=path.name,
        format=document_format,
        character_count=len(normalized_text),
        page_count=page_count,
    )
    return ExtractedDocument(text=normalized_text, metadata=metadata)


def _extract_pdf(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages_text)
    if not text.strip():
        raise EmptyPdfTextError(
            f"El PDF '{path.name}' no contiene texto extraíble; OCR está fuera de alcance."
        )
    return text, len(reader.pages)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()