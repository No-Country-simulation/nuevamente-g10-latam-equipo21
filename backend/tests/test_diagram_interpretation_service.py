from types import SimpleNamespace

from app.services.diagram_interpretation_service import (
    DiagramInterpretationService,
)
from app.services.document_ingestion import ExtractedImage


class FakeModels:
    def generate_content(self, model, contents):
        return SimpleNamespace(
            text=(
                "El diagrama muestra un cliente conectado a una API, "
                "que posteriormente se comunica con una base de datos."
            )
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