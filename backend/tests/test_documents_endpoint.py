import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.output import AlmacenamientoOCISchema
from app.services.oci_storage_service import get_oci_storage_service_factory
from app.services.diagram_interpretation_service import (
    InterpretedDiagram,
    get_diagram_interpretation_service,
)
from app.services.document_ingestion import (
    DocumentMetadata,
    ExtractedDocument,
    ExtractedImage,
)


client = TestClient(app)
_LOGGER = "app.api.v1.endpoints.documents"


class FakeStorageService:
    def upload_original(self, *, filename, content, content_type):
        assert filename == "lesson.md"
        assert content == b"# Lesson\r\n\r\nContent.  "
        assert content_type == "text/markdown"
        return AlmacenamientoOCISchema(
            bucket="test-bucket",
            objeto_id="originales/test-lesson.md",
            status_upload="completado",
        )

class FakeDiagramInterpretationService:
    def interpret(self, image):
        return InterpretedDiagram(
            description=(
                "El diagrama muestra un cliente conectado a una API "
                "que se comunica con una base de datos."
            ),
            page_number=image.page_number,
            image_index=image.image_index,
            image_name=image.name,
        )


@pytest.fixture(autouse=True)
def _override_storage_service():
    app.dependency_overrides[get_oci_storage_service_factory] = lambda: FakeStorageService
    yield
    app.dependency_overrides.pop(get_oci_storage_service_factory, None)


def test_extract_document_endpoint_returns_text_and_metadata():
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("lesson.md", b"# Lesson\r\n\r\nContent.  ", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "# Lesson\n\nContent.",
        "metadata": {
            "filename": "lesson.md",
            "format": "md",
            "character_count": len("# Lesson\n\nContent."),
            "page_count": None,
        },
    }


def test_extract_document_endpoint_continues_when_storage_factory_fails(caplog):
    def unavailable_storage_factory():
        raise ValueError("OCI namespace is not configured")

    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: unavailable_storage_factory
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        response = client.post(
            "/api/v1/documents/extract",
            files={"file": ("lesson.md", b"# Lesson\r\n\r\nContent.  ", "text/markdown")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "text": "# Lesson\n\nContent.",
        "metadata": {
            "filename": "lesson.md",
            "format": "md",
            "character_count": len("# Lesson\n\nContent."),
            "page_count": None,
        },
    }
    assert "ValueError" in caplog.text
    assert "OCI namespace is not configured" not in caplog.text


def test_extract_document_endpoint_returns_readable_error_for_unsupported_format():
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("lesson.docx", b"unsupported", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Formatos permitidos" in response.json()["detail"]

def test_extract_document_endpoint_returns_interpreted_diagrams(monkeypatch):
    app.dependency_overrides[get_diagram_interpretation_service] = (
        lambda: FakeDiagramInterpretationService()
    )

    fake_document = ExtractedDocument(
        text="Arquitectura del sistema",
        metadata=DocumentMetadata(
            filename="diagram.pdf",
            format="pdf",
            character_count=len("Arquitectura del sistema"),
            page_count=1,
        ),
        images=(
            ExtractedImage(
                data=b"fake-image-data",
                name="diagram.png",
                page_number=1,
                image_index=1,
                mime_type="image/png",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.extract_document",
        lambda path: fake_document,
    )
    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: lambda: None
    )
    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "diagram.pdf",
                b"fake-pdf-content",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["diagramas"] == [
        {
            "description": (
                "El diagrama muestra un cliente conectado a una API "
                "que se comunica con una base de datos."
            ),
            "page_number": 1,
            "image_index": 1,
            "image_name": "diagram.png",
        }
    ]