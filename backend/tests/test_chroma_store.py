from app.services.chunking import TextChunk
from app.services.chroma_store import ChromaStore


class FakeEmbeddingService:
    """
    Servicio falso para no llamar a Gemini durante los tests.
    """

    def embed_documents(self, texts):
        return [
            [
                float(index + 1),
                float(len(text)),
                0.5,
            ]
            for index, text in enumerate(texts)
        ]


def build_chunks():
    return [
        TextChunk(
            document_id="doc-001",
            chunk_index=0,
            text="Primera parte del documento.",
            page_number=1,
            char_start=0,
            char_end=28,
        ),
        TextChunk(
            document_id="doc-001",
            chunk_index=1,
            text="Segunda parte del documento.",
            page_number=2,
            char_start=0,
            char_end=28,
        ),
    ]


def test_index_chunks(tmp_path):
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )

    cantidad = store.index_chunks(
        build_chunks()
    )

    assert cantidad == 2
    assert store.count_document("doc-001") == 2


def test_reindex_is_idempotent(tmp_path):
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )

    chunks = build_chunks()

    store.index_chunks(chunks)
    store.index_chunks(chunks)

    assert store.count_document("doc-001") == 2


def test_chroma_persists_after_new_instance(tmp_path):
    persist_directory = str(tmp_path)

    first_store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=persist_directory,
    )

    first_store.index_chunks(
        build_chunks()
    )

    # Simula que cerramos y volvemos
    # a levantar el proceso.
    second_store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=persist_directory,
    )

    assert second_store.count_document(
        "doc-001"
    ) == 2


def test_reindex_removes_old_chunks(tmp_path):
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )

    chunks = build_chunks()

    store.index_chunks(chunks)

    store.index_chunks(
        [chunks[0]]
    )

    assert store.count_document("doc-001") == 1