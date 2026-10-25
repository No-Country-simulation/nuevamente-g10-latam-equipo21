import json

import oci
import pytest

from app.core.config import Settings
from app.schemas.input import InputSchema
from app.services.mock_adaptacion_service import construir_respuesta_mock
from app.services.oci_storage_service import (
    OCIStorageService,
    build_generated_object_name,
    build_object_storage_client,
    build_original_object_name,
)
from app.core.errors import OCIAuthenticationError


class RecordingObjectStorageClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def _payload() -> InputSchema:
    return InputSchema(
        documento_titulo="Introducción a OCI / VCN",
        documento_contenido="Contenido técnico suficientemente extenso para adaptar.",
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Didactico",
        documento_id="doc-test-original",
        objeto_origen_id="originales/lesson-source.md",
    )


def test_original_object_name_is_deterministic_and_rejects_client_paths():
    content = b"same document"

    first = build_original_object_name("../../Lección Final.PDF", content)
    second = build_original_object_name(r"C:\uploads\Lección Final.PDF", content)

    assert first == second
    assert first.startswith("originales/")
    assert first.endswith("-leccion-final.pdf")
    assert ".." not in first
    assert "\\" not in first


def test_generated_object_name_matches_brief_and_is_deterministic():
    payload = _payload()

    first = build_generated_object_name(payload)
    second = build_generated_object_name(payload)

    assert first == second
    assert first.startswith("contenido-introduccion-a-oci-vcn-principiante-flashcards-")
    assert first.endswith(".json")


def test_upload_original_sends_exact_bytes_and_content_type():
    client = RecordingObjectStorageClient()
    service = OCIStorageService(
        client,
        namespace="test-namespace",
        bucket_name="test-bucket",
    )

    result = service.upload_original(
        filename="lesson.md",
        content=b"original bytes",
        content_type="text/markdown",
    )

    assert result.status_upload == "completado"
    assert result.bucket == "test-bucket"
    assert result.objeto_id == build_original_object_name(
        "lesson.md", b"original bytes"
    )
    assert len(client.calls) == 1
    assert client.calls[0]["namespace_name"] == "test-namespace"
    assert client.calls[0]["bucket_name"] == "test-bucket"
    assert client.calls[0]["put_object_body"] == b"original bytes"
    assert client.calls[0]["content_type"] == "text/markdown"


def test_generated_package_is_uploaded_as_json_with_storage_result():
    client = RecordingObjectStorageClient()
    service = OCIStorageService(
        client,
        namespace="test-namespace",
        bucket_name="test-bucket",
    )
    payload = _payload()
    response = construir_respuesta_mock(payload)

    result = service.persist_generated_package(
        payload=payload,
        response=response,
    )

    assert result.status == "exito"
    assert result.almacenamiento_oci.status_upload == "completado"
    assert result.almacenamiento_oci.objeto_id == build_generated_object_name(payload)
    assert result.almacenamiento_oci.documento_id == "doc-test-original"
    assert result.almacenamiento_oci.objeto_origen_id == "originales/lesson-source.md"

    uploaded = json.loads(
        client.calls[0]["put_object_body"].decode("utf-8")
    )

    assert (
        uploaded["contenido_adaptado"]
        == result.contenido_adaptado.model_dump(mode="json")
    )
    assert uploaded["almacenamiento_oci"]["status_upload"] == "completado"
    assert uploaded["almacenamiento_oci"]["documento_id"] == "doc-test-original"
    assert (
        uploaded["almacenamiento_oci"]["objeto_origen_id"]
        == "originales/lesson-source.md"
    )
    assert client.calls[0]["content_type"] == "application/json"


def test_upload_failure_preserves_generated_content_and_reports_error(caplog):
    client = RecordingObjectStorageClient(
        error=RuntimeError("secret must not be logged")
    )
    service = OCIStorageService(
        client,
        namespace="test-namespace",
        bucket_name="test-bucket",
    )
    payload = _payload()
    response = construir_respuesta_mock(payload)

    result = service.persist_generated_package(
        payload=payload,
        response=response,
    )

    assert result.status == response.status
    assert result.contenido_adaptado == response.contenido_adaptado
    assert result.almacenamiento_oci.status_upload == "error"
    assert "secret must not be logged" not in caplog.text


def test_upload_failure_logs_request_id_without_exposing_error_message(
    caplog,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.oci_storage_service.get_request_id",
        lambda: "req-test-123",
    )

    client = RecordingObjectStorageClient(
        error=RuntimeError("secret must not be logged")
    )
    service = OCIStorageService(
        client,
        namespace="test-namespace",
        bucket_name="test-bucket",
    )

    result = service.upload_original(
        filename="lesson.md",
        content=b"original bytes",
        content_type="text/markdown",
    )

    assert result.status_upload == "error"
    assert "req-test-123" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "secret must not be logged" not in caplog.text


def test_put_object_failure_returns_error_and_original_object_key():
    client = RecordingObjectStorageClient(error=RuntimeError("upload failed"))
    service = OCIStorageService(
        client,
        namespace="test-namespace",
        bucket_name="test-bucket",
    )

    result = service.upload_original(
        filename="lesson.md",
        content=b"original bytes",
        content_type="text/markdown",
    )

    assert result.status_upload == "error"
    assert result.objeto_id == build_original_object_name(
        "lesson.md", b"original bytes"
    )
    assert result.objeto_id != "lesson.md"


@pytest.mark.parametrize("status_code", [401, 403])
def test_authentication_or_permission_failure_raises_oci_authentication_error(
    status_code,
    caplog,
):
    client = RecordingObjectStorageClient(
        error=oci.exceptions.ServiceError(
            status=status_code,
            code="NotAuthorized",
            headers={},
            message="sensitive OCI detail",
        )
    )
    service = OCIStorageService(
        client,
        namespace="test-namespace",
        bucket_name="test-bucket",
    )

    with pytest.raises(OCIAuthenticationError):
        service.upload_original(
            filename="lesson.md",
            content=b"original bytes",
            content_type="text/markdown",
        )

    assert "ServiceError" in caplog.text
    assert "sensitive OCI detail" not in caplog.text


def test_client_uses_instance_principal_without_static_credentials(monkeypatch):
    signer = object()
    captured = {}

    monkeypatch.setattr(
        oci.auth.signers,
        "InstancePrincipalsSecurityTokenSigner",
        lambda: signer,
    )

    monkeypatch.setattr(
        oci.object_storage,
        "ObjectStorageClient",
        lambda config, **kwargs: captured.update(
            config=config,
            **kwargs,
        )
        or object(),
    )

    app_settings = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        OCI_AUTH_MODE="instance_principal",
        _env_file=None,
    )

    build_object_storage_client(app_settings)

    assert captured == {
        "config": {},
        "signer": signer,
    }


def test_api_key_mode_reads_complete_configuration_from_settings(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        oci.config,
        "validate_config",
        lambda config: None,
    )

    monkeypatch.setattr(
        oci.object_storage,
        "ObjectStorageClient",
        lambda config: captured.update(config=config) or object(),
    )

    app_settings = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        OCI_AUTH_MODE="api_key",
        OCI_USER_OCID="user-from-env",
        OCI_TENANCY_OCID="tenancy-from-env",
        OCI_FINGERPRINT="fingerprint-from-env",
        OCI_KEY_FILE="key-file-from-env",
        OCI_KEY_PASSPHRASE="passphrase-from-env",
        OCI_REGION="region-from-env",
        _env_file=None,
    )

    build_object_storage_client(app_settings)

    assert captured["config"] == {
        "user": "user-from-env",
        "tenancy": "tenancy-from-env",
        "fingerprint": "fingerprint-from-env",
        "key_file": "key-file-from-env",
        "pass_phrase": "passphrase-from-env",
        "region": "region-from-env",
    }


def test_api_key_mode_reports_missing_environment_variable_names():
    app_settings = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        OCI_AUTH_MODE="api_key",
        OCI_REGION="sa-saopaulo-1",
        _env_file=None,
    )

    with pytest.raises(ValueError, match="OCI_USER_OCID"):
        build_object_storage_client(app_settings)


@pytest.mark.parametrize("auth_mode", ["instance_principal", "api_key"])
def test_oci_client_initialization_failure_raises_authentication_error(
    monkeypatch, caplog, auth_mode
):
    if auth_mode == "instance_principal":
        monkeypatch.setattr(
            oci.auth.signers,
            "InstancePrincipalsSecurityTokenSigner",
            lambda: (_ for _ in ()).throw(RuntimeError("private init detail")),
        )
    else:
        monkeypatch.setattr(oci.config, "validate_config", lambda config: None)
        monkeypatch.setattr(
            oci.object_storage,
            "ObjectStorageClient",
            lambda config: (_ for _ in ()).throw(RuntimeError("private init detail")),
        )
    app_settings = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        OCI_AUTH_MODE=auth_mode,
        OCI_USER_OCID="user",
        OCI_TENANCY_OCID="tenancy",
        OCI_FINGERPRINT="fingerprint",
        OCI_KEY_FILE="key-file",
        OCI_REGION="region",
        _env_file=None,
    )
    with pytest.raises(OCIAuthenticationError):
        build_object_storage_client(app_settings)

    assert "RuntimeError" in caplog.text
    assert "private init detail" not in caplog.text