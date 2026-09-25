from dataclasses import dataclass
from typing import List


DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


@dataclass
class TextChunk:
    document_id: str
    chunk_index: int
    text: str
    page_number: int
    char_start: int
    char_end: int


def chunk_pages(
    document_id: str,
    pages: List[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[TextChunk]:
    """
    Divide el contenido de un documento en fragmentos (chunks).

    Cada elemento de pages debe tener esta forma:

        {
            "page_number": 1,
            "text": "contenido de la página..."
        }

    Los chunks conservan metadata de trazabilidad:
    - document_id
    - chunk_index
    - page_number
    - char_start
    - char_end
    """

    if not document_id.strip():
        raise ValueError("document_id no puede estar vacío.")

    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que 0.")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap no puede ser negativo.")

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap debe ser menor que chunk_size."
        )

    chunks: List[TextChunk] = []
    chunk_index = 0

    for page in pages:
        page_number = page.get("page_number")
        text = page.get("text", "")

        if page_number is None:
            raise ValueError(
                "Cada página debe incluir page_number."
            )

        if not isinstance(text, str):
            raise ValueError(
                "El contenido de text debe ser un string."
            )

        text = text.strip()

        if not text:
            continue

        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            chunk_text = text[start:end]

            chunks.append(
                TextChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    text=chunk_text,
                    page_number=page_number,
                    char_start=start,
                    char_end=end,
                )
            )

            chunk_index += 1

            if end >= len(text):
                break

            start = end - chunk_overlap

    return chunks