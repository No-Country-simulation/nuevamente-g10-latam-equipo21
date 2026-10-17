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


@pytest.mark.parametrize(
    "total, expected_batches",
    [
        (100, [100]),
        (101, [100, 1]),
        (200, [100, 100]),
        (250, [100, 100, 50]),
    ],
)
def test_embeddings_are_processed_in_batches(
    total, expected_batches
):
    """Verifica tamaño, cantidad y orden de los lotes."""

    class RecordingModels:
        def __init__(self):
            self.batches = []

        def embed_content(self, **kwargs):
            contents = kwargs["contents"]
            self.batches.append(list(contents))

            assert len(contents) <= 100

            return FakeBatchResponse([
                FakeEmbedding([float(text.split("-")[1])])
                for text in contents
            ])

    class RecordingClient:
        def __init__(self):
            self.models = RecordingModels()

    class FakeBatchResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

    client = RecordingClient()
    service = GeminiEmbeddingService(client=client)

    texts = [f"fragmento-{i}" for i in range(total)]
    vectors = service.embed_documents(texts)

    assert [len(batch) for batch in client.models.batches] == (
        expected_batches
    )

    assert len(vectors) == total

    assert vectors == [
        [float(i)] for i in range(total)
    ]

    assert [
        text
        for batch in client.models.batches
        for text in batch
    ] == texts


def test_failed_batch_does_not_return_partial_results():
    """Si falla el segundo lote, el servicio lanza un error."""

    class FailingModels:
        def __init__(self):
            self.calls = 0

        def embed_content(self, **kwargs):
            self.calls += 1

            if self.calls == 2:
                raise RuntimeError("Fallo simulado de Gemini")

            return FakeBatchResponse([
                FakeEmbedding([float(i)])
                for i, _ in enumerate(kwargs["contents"])
            ])

    class FakeBatchResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

    class FailingClient:
        def __init__(self):
            self.models = FailingModels()

    client = FailingClient()
    service = GeminiEmbeddingService(client=client)

    texts = [f"fragmento-{i}" for i in range(150)]

    with pytest.raises(
        EmbeddingServiceError,
        match="lote 2",
    ):
        service.embed_documents(texts)

    assert client.models.calls == 2


def test_incomplete_batch_raises_error():
    """Gemini debe devolver un vector por cada fragmento."""

    class IncompleteModels:
        def embed_content(self, **kwargs):
            return FakeBatchResponse([
                FakeEmbedding([0.1, 0.2])
            ])

    class FakeBatchResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

    class IncompleteClient:
        def __init__(self):
            self.models = IncompleteModels()

    service = GeminiEmbeddingService(
        client=IncompleteClient()
    )

    with pytest.raises(
        EmbeddingServiceError,
        match="Cantidad incorrecta",
    ):
        service.embed_documents(["uno", "dos"])
