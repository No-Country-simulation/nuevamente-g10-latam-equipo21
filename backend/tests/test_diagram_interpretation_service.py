from types import SimpleNamespace

from app.core.config import settings
from app.services.diagram_interpretation_service import DiagramInterpretationService
from app.services.document_ingestion import ExtractedImage


class FakeModels:
    def generate_content(self, model, contents):
        return SimpleNamespace(
            text="El diagrama muestra un cliente conectado a una API."
        )


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


def test_interprets_diagram_and_preserves_origin():
    image = ExtractedImage(
        data=b"fake-image-data",
        name="diagram.png",
        page_number=3,
        image_index=2,
        mime_type="image/png",
    )
    service = DiagramInterpretationService(
        model_name="fake-multimodal-model",
        client=FakeClient(),
    )

    result = service.interpret(image)

    assert "cliente conectado a una API" in result.description
    assert result.page_number == 3
    assert result.image_index == 2
    assert result.image_name == "diagram.png"


def test_configures_multimodal_client_timeout_in_milliseconds(monkeypatch):
    observed = {}
    fake_client = FakeClient()

    def client_factory(*, api_key, http_options):
        observed["api_key"] = api_key
        observed["timeout"] = http_options.timeout
        return fake_client

    monkeypatch.setattr(
        "app.services.diagram_interpretation_service.genai.Client",
        client_factory,
    )
    monkeypatch.setattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.5)

    service = DiagramInterpretationService(api_key="test-key")

    assert service.client is fake_client
    assert observed == {"api_key": "test-key", "timeout": 12_500}
