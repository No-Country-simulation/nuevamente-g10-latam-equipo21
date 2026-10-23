import pytest

from app.services.embeddings import (
    EmbeddingServiceError,
    GeminiEmbeddingService,
)

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


def test_failed_embedding_batch_preserves_existing_chunks(tmp_path):
    """
    Si Gemini falla durante el segundo lote:
    - No se indexan fragmentos nuevos.
    - Se conserva la versión anterior del documento.
    - Se propaga EmbeddingServiceError.
    """

    class FakeEmbedding:
        def __init__(self, values):
            self.values = values

    class FakeResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

    class FailingModels:
        def __init__(self):
            self.calls = 0

        def embed_content(self, **kwargs):
            self.calls += 1

            if self.calls == 2:
                raise RuntimeError(
                    "Fallo simulado en el segundo lote"
                )

            return FakeResponse([
                FakeEmbedding([
                    float(index + 1),
                    float(len(text)),
                    0.5,
                ])
                for index, text in enumerate(
                    kwargs["contents"]
                )
            ])

    class FailingClient:
        def __init__(self):
            self.models = FailingModels()

    # Primero indexamos correctamente un documento.
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )

    original_chunks = build_chunks()
    store.index_chunks(original_chunks)

    assert store.count_document("doc-001") == 2

    original_data = store.collection.get(
        where={"document_id": "doc-001"},
        include=["documents"],
    )

    original_documents = dict(zip(
        original_data["ids"],
        original_data["documents"],
    ))

    # Simulamos una nueva versión con 150 fragmentos.
    # Gemini procesará correctamente los primeros 100,
    # pero fallará al intentar procesar los siguientes 50.
    new_chunks = [
        TextChunk(
            document_id="doc-001",
            chunk_index=index,
            text=f"Fragmento actualizado numero {index}",
            page_number=1,
            char_start=index * 40,
            char_end=index * 40 + 30,
        )
        for index in range(150)
    ]

    client = FailingClient()

    store.embedding_service = GeminiEmbeddingService(
        client=client
    )

    # Verificamos que el error llegue al consumidor.
    with pytest.raises(
        EmbeddingServiceError,
        match="lote 2",
    ):
        store.index_chunks(new_chunks)

    assert client.models.calls == 2

    # No debe haberse eliminado la versión anterior.
    assert store.count_document("doc-001") == 2

    current_data = store.collection.get(
        where={"document_id": "doc-001"},
        include=["documents"],
    )

    current_documents = dict(zip(
        current_data["ids"],
        current_data["documents"],
    ))

    assert current_documents == original_documents
