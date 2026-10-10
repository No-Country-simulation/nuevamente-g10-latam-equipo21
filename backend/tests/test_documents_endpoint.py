import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.output import AlmacenamientoOCISchema
from app.services.oci_storage_service import get_oci_storage_service_factory

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
    data = response.json()

    assert "documento_id" in data
    assert data["objeto_id"] == {
        "documento_id": None,
        "bucket": "test-bucket",
        "objeto_id": "originales/test-lesson.md",
        "status_upload": "completado",
    } or data["objeto_id"] == "originales/test-lesson.md"
    assert data["status_upload"] == "completado"
    assert data["text"] == "# Lesson\n\nContent."
    assert data["metadata"] == {
        "filename": "lesson.md",
        "format": "md",
        "character_count": len("# Lesson\n\nContent."),
        "page_count": None,
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
    data = response.json()

    assert "documento_id" in data
    assert data["status_upload"] == "error"
    assert data["text"] == "# Lesson\n\nContent."
    assert data["metadata"] == {
        "filename": "lesson.md",
        "format": "md",
        "character_count": len("# Lesson\n\nContent."),
        "page_count": None,
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