import pytest

from app.services.chunking import (
    chunk_pages,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)


def test_chunk_document_preserves_metadata():
    pages = [
        {
            "page_number": 1,
            "text": "A" * 1500,
        },
        {
            "page_number": 2,
            "text": "B" * 500,
        },
    ]

    chunks = chunk_pages(
        document_id="doc-001",
        pages=pages,
    )

    assert len(chunks) == 3

    assert chunks[0].document_id == "doc-001"
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == DEFAULT_CHUNK_SIZE

    assert chunks[1].chunk_index == 1
    assert chunks[1].page_number == 1
    assert chunks[1].char_start == (
        DEFAULT_CHUNK_SIZE - DEFAULT_CHUNK_OVERLAP
    )

    assert chunks[2].chunk_index == 2
    assert chunks[2].page_number == 2


def test_chunk_size_and_overlap_are_configurable():
    pages = [
        {
            "page_number": 1,
            "text": "X" * 1000,
        }
    ]

    chunks = chunk_pages(
        document_id="doc-002",
        pages=pages,
        chunk_size=400,
        chunk_overlap=100,
    )

    assert len(chunks) == 3
    assert chunks[0].char_start == 0
    assert chunks[1].char_start == 300
    assert chunks[2].char_start == 600


def test_invalid_overlap_raises_error():
    pages = [
        {
            "page_number": 1,
            "text": "Contenido de prueba",
        }
    ]

    with pytest.raises(ValueError):
        chunk_pages(
            document_id="doc-003",
            pages=pages,
            chunk_size=100,
            chunk_overlap=100,
        )


def test_empty_pages_are_ignored():
    pages = [
        {
            "page_number": 1,
            "text": "",
        },
        {
            "page_number": 2,
            "text": "Contenido válido",
        },
    ]

    chunks = chunk_pages(
        document_id="doc-004",
        pages=pages,
    )

    assert len(chunks) == 1
    assert chunks[0].page_number == 2