import logging
from pathlib import Path
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import settings
from app.core.errors import OCIAuthenticationError
from app.main import app
from app.schemas.output import AlmacenamientoOCISchema
from app.services.diagram_interpretation_service import (
    DiagramInterpretationError,
    InterpretedDiagram,
    get_diagram_interpretation_service,
)
from app.services.document_ingestion import (
    DocumentMetadata,
    ExtractedDocument,
    ExtractedImage,
)
from app.services.document_identity import documento_id_desde_contenido
from app.services.oci_storage_service import get_oci_storage_service_factory

FIXTURES_DIR = Path(__file__).parent / "fixtures"

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
            description="Un cliente se conecta a la API y a la base de datos.",
            page_number=image.page_number,
            image_index=image.image_index,
            image_name=image.name,
        )


class PermissiveStorageService:
    def upload_original(self, **kwargs):
        return None


class FailingDiagramInterpretationService:
    def interpret(self, image):
        raise DiagramInterpretationError("detalle técnico que no debe exponerse")


@pytest.fixture(autouse=True)
def _override_storage_service():
    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: FakeStorageService
    )
    yield
    app.dependency_overrides.pop(
        get_oci_storage_service_factory,
        None,
    )
    app.dependency_overrides.pop(
        get_diagram_interpretation_service,
        None,
    )


def test_extract_document_endpoint_returns_text_and_metadata():
    diagram_service = FakeDiagramInterpretationService()
    diagram_service.interpret = pytest.fail
    app.dependency_overrides[get_diagram_interpretation_service] = (
        lambda: diagram_service
    )

    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "lesson.md",
                b"# Lesson\r\n\r\nContent.  ",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["documento_id"] == documento_id_desde_contenido(data["text"])
    assert data["objeto_id"] == "originales/test-lesson.md"
    assert data["status_upload"] == "completado"
    assert data["text"] == "# Lesson\n\nContent."
    assert "diagramas" not in data
    assert data["metadata"] == {
        "filename": "lesson.md",
        "format": "md",
        "character_count": len("# Lesson\n\nContent."),
        "page_count": None,
    }

    repeated_response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "lesson.md",
                b"# Lesson\r\n\r\nContent.  ",
                "text/markdown",
            )
        },
    )
    assert repeated_response.json()["documento_id"] == data["documento_id"]


def test_extract_document_endpoint_returns_interpreted_diagrams(monkeypatch):
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
        lambda *args, **kwargs: fake_document,
    )
    app.dependency_overrides[get_diagram_interpretation_service] = (
        lambda: FakeDiagramInterpretationService()
    )
    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: PermissiveStorageService
    )

    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("diagram.pdf", b"fake-pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["diagramas"] == [
        {
            "description": "Un cliente se conecta a la API y a la base de datos.",
            "page_number": 1,
            "image_index": 1,
            "image_name": "diagram.png",
        }
    ]


def test_extract_document_endpoint_skips_failed_diagram_and_returns_text(monkeypatch):
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
        lambda *args, **kwargs: fake_document,
    )
    app.dependency_overrides[get_diagram_interpretation_service] = (
        lambda: FailingDiagramInterpretationService()
    )
    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: PermissiveStorageService
    )

    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("diagram.pdf", b"fake-pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Arquitectura del sistema"
    assert "diagramas" not in response.json()


def test_extract_document_endpoint_skips_small_images_before_gemini(monkeypatch):
    fake_document = ExtractedDocument(
        text="Arquitectura del sistema",
        metadata=DocumentMetadata(
            filename="icon.pdf",
            format="pdf",
            character_count=len("Arquitectura del sistema"),
            page_count=1,
        ),
        images=(
            ExtractedImage(
                data=b"fake-image-data",
                name="icon.png",
                page_number=1,
                image_index=1,
                mime_type="image/png",
                width=20,
                height=20,
            ),
        ),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.extract_document",
        lambda *args, **kwargs: fake_document,
    )
    monkeypatch.setattr(settings, "DIAGRAM_MIN_IMAGE_AREA_PIXELS", 10_000)
    diagram_service = FakeDiagramInterpretationService()
    diagram_service.interpret = pytest.fail
    app.dependency_overrides[get_diagram_interpretation_service] = (
        lambda: diagram_service
    )
    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: PermissiveStorageService
    )

    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("icon.pdf", b"fake-pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    assert "diagramas" not in response.json()


def test_extract_document_endpoint_rejects_too_many_images_before_gemini(monkeypatch):
    images = tuple(
        ExtractedImage(
            data=b"fake-image-data",
            name=f"diagram-{index}.png",
            page_number=1,
            image_index=index,
            mime_type="image/png",
        )
        for index in range(1, 3)
    )
    fake_document = ExtractedDocument(
        text="Arquitectura del sistema",
        metadata=DocumentMetadata(
            filename="many-diagrams.pdf",
            format="pdf",
            character_count=len("Arquitectura del sistema"),
            page_count=1,
        ),
        images=images,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.extract_document",
        lambda *args, **kwargs: fake_document,
    )
    monkeypatch.setattr(settings, "DIAGRAM_MAX_IMAGES_PER_DOCUMENT", 1)
    diagram_service = FakeDiagramInterpretationService()
    diagram_service.interpret = pytest.fail
    app.dependency_overrides[get_diagram_interpretation_service] = (
        lambda: diagram_service
    )
    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: (lambda: pytest.fail("No debe persistir un documento inválido"))
    )

    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("many-diagrams.pdf", b"fake-pdf-content", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["codigo"] == "DOCUMENTO_INVALIDO"
    assert "2 imágenes" in response.json()["error"]["mensaje"]
    assert "máximo permitido es 1" in response.json()["error"]["mensaje"]


def test_extract_document_endpoint_continues_when_storage_factory_fails(
    caplog,
):
    def unavailable_storage_factory():
        raise ValueError("OCI namespace is not configured")

    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: unavailable_storage_factory
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        response = client.post(
            "/api/v1/documents/extract",
            files={
                "file": (
                    "lesson.md",
                    b"# Lesson\r\n\r\nContent.  ",
                    "text/markdown",
                )
            },
        )

    assert response.status_code == 200
    data = response.json()

    assert "documento_id" in data
    assert data["status_upload"] == "error"
    assert data["objeto_id"] is None
    assert data["text"] == "# Lesson\n\nContent."
    assert data["metadata"] == {
        "filename": "lesson.md",
        "format": "md",
        "character_count": len("# Lesson\n\nContent."),
        "page_count": None,
    }

    assert "ValueError" in caplog.text
    assert "OCI namespace is not configured" not in caplog.text


def test_extract_document_endpoint_preserves_original_upload_error_status():
    class FailedStorageService:
        def upload_original(self, **kwargs):
            return AlmacenamientoOCISchema(
                bucket="test-bucket",
                objeto_id="originales/failed-upload.md",
                status_upload="error",
            )

    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: FailedStorageService
    )
    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "lesson.md",
                b"# Lesson\r\n\r\nContent.  ",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["status_upload"] == "error"
    assert response.json()["objeto_id"] == "originales/failed-upload.md"


def test_extract_document_endpoint_returns_502_when_oci_authentication_fails():
    """
    NM-25:
    una falla de autenticación OCI debe ser visible para el cliente
    y no quedar oculta como una persistencia opcional fallida.
    """

    def authentication_failure():
        raise OCIAuthenticationError()

    app.dependency_overrides[get_oci_storage_service_factory] = (
        lambda: authentication_failure
    )

    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "lesson.md",
                b"# Lesson\r\n\r\nContent.  ",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "status": "error",
        "error": {
            "codigo": "OCI_AUTENTICACION_ERROR",
            "mensaje": (
                "No fue posible autenticarse con OCI Object Storage. "
                "Verifica la configuración de credenciales e intenta nuevamente."
            ),
        },
    }


def test_extract_document_endpoint_returns_contract_error_for_unsupported_format():
    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "lesson.docx",
                b"unsupported",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "FORMATO_NO_SOPORTADO"
    assert "Formatos permitidos" in body["error"]["mensaje"]


def test_extract_document_endpoint_returns_contract_error_for_pdf_without_text():
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("scanned.pdf", _pdf_sin_texto(), "application/pdf")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "PDF_SIN_TEXTO"

def test_pdf_sin_texto_muestra_nombre_original():
    filename = "05_pdf_escaneado_sin_texto.pdf"

    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                filename,
                _pdf_sin_texto(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "PDF_SIN_TEXTO"

    mensaje = body["error"]["mensaje"]

    assert filename in mensaje
    assert "no contiene texto extraíble" in mensaje
    assert "tmp" not in mensaje

def _pdf_sin_texto() -> bytes:
    """PDF de una página en blanco (sin capa de texto) para el caso EmptyPdfTextError."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()

def test_extract_document_endpoint_rejects_empty_file():
    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "07_archivo_vacio.txt",
                b"",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "DOCUMENTO_INVALIDO"
    assert "07_archivo_vacio.txt" in body["error"]["mensaje"]
    assert "vacío" in body["error"]["mensaje"]

def test_fixture_latin1_devuelve_error_controlado():
    contenido = (
        FIXTURES_DIR / "10_texto_latin1.txt"
    ).read_bytes()

    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("10_texto_latin1.txt", contenido, "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["codigo"] == "DOCUMENTO_INVALIDO"


def test_fixture_pdf_escaneado_muestra_nombre_original():
    contenido = (
        FIXTURES_DIR / "05_pdf_escaneado_sin_texto.pdf"
    ).read_bytes()

    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "05_pdf_escaneado_sin_texto.pdf",
                contenido,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["codigo"] == "PDF_SIN_TEXTO"
    assert "05_pdf_escaneado_sin_texto.pdf" in body["error"]["mensaje"]


def test_fixture_archivo_vacio_devuelve_400():
    contenido = (
        FIXTURES_DIR / "07_archivo_vacio.txt"
    ).read_bytes()

    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("07_archivo_vacio.txt", contenido, "text/plain")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["codigo"] == "DOCUMENTO_INVALIDO"
    assert "vacío" in body["error"]["mensaje"]

def test_archivo_sin_extension_muestra_nombre_original():
    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "sin_extension",
                b"Contenido de prueba",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400

    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "FORMATO_NO_SOPORTADO"
    assert "sin_extension" in body["error"]["mensaje"]
    assert "Formatos permitidos" in body["error"]["mensaje"]
    assert "tmp" not in body["error"]["mensaje"]


def test_latin1_muestra_nombre_original_del_archivo():
    filename = "10_texto_latin1.txt"

    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                filename,
                "Información técnica en español".encode("latin-1"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "DOCUMENTO_INVALIDO"

    mensaje = body["error"]["mensaje"]
    assert filename in mensaje
    assert "UTF-8" in mensaje
    assert ".tmp" not in mensaje


def test_extract_document_endpoint_rejects_zero_byte_pdf():
    """Un PDF de cero bytes debe devolver 400, nunca 500."""
    response = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "documento_vacio.pdf",
                b"",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "DOCUMENTO_INVALIDO"
    assert "documento_vacio.pdf" in body["error"]["mensaje"]
    assert "vacío" in body["error"]["mensaje"]
