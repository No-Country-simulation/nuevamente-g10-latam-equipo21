import pytest

from app.services.embeddings import (
    EmbeddingServiceError,
    GeminiEmbeddingService,
)


class FakeEmbedding:
    def __init__(self, values):
        self.values = values


class FakeResponse:
    def __init__(self):
        self.embeddings = [
            FakeEmbedding([0.1, 0.2, 0.3]),
            FakeEmbedding([0.4, 0.5, 0.6]),
        ]


class FakeModels:
    def embed_content(self, **kwargs):
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


def test_embed_documents_returns_vectors():
    service = GeminiEmbeddingService(
        client=FakeClient()
    )

    vectors = service.embed_documents(
        [
            "La VCN es una red virtual.",
            "Una subnet pertenece a una VCN.",
        ]
    )

    assert len(vectors) == 2
    assert vectors[0] == [0.1, 0.2, 0.3]
    assert vectors[1] == [0.4, 0.5, 0.6]


def test_embed_empty_list_returns_empty_list():
    service = GeminiEmbeddingService(
        client=FakeClient()
    )

    vectors = service.embed_documents([])

    assert vectors == []


def test_empty_document_raises_error():
    service = GeminiEmbeddingService(
        client=FakeClient()
    )

    with pytest.raises(ValueError):
        service.embed_documents([""])


def test_missing_api_key_raises_error():
    with pytest.raises(EmbeddingServiceError):
        GeminiEmbeddingService(api_key="")