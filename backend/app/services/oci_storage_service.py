"""Persistencia de documentos y paquetes educativos en OCI Object Storage."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol

import oci

from app.core.config import Settings, settings
from app.core.request_context import get_request_id
from app.schemas.input import InputSchema
from app.schemas.output import AlmacenamientoOCISchema, OutputSchema


logger = logging.getLogger(__name__)


class ObjectStorageClientProtocol(Protocol):
    def put_object(self, **kwargs: Any) -> Any: ...


def _slug(value: str, *, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return (slug or "sin-valor")[:max_length].rstrip("-")


def build_original_object_name(filename: str, content: bytes) -> str:
    """Genera una clave estable y segura sin aceptar rutas del cliente."""
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    path = Path(basename)
    suffix = path.suffix.lower()
    safe_suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ""
    digest = sha256(content).hexdigest()[:16]
    return f"originales/{digest}-{_slug(path.stem)}{safe_suffix}"


def build_generated_object_name(payload: InputSchema) -> str:
    """
    Construye un nombre de objeto determinista e idempotente para OCI.

    Decisión de diseño (NM-27):
    A partir de los metadatos y el hash canónico del payload de entrada, se genera
    un nombre fijo. Peticiones con la misma entrada generarán exactamente el mismo
    'objeto_id', asegurando que la operación sea idempotente y sobrescriba el objeto
    previo en el bucket.
    """
    canonical_payload = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    sequence = sha256(canonical_payload).hexdigest()[:12]
    return (
        f"contenido-{_slug(payload.documento_titulo)}-"
        f"{_slug(payload.perfil_destinatario.value)}-"
        f"{_slug(payload.formato_salida.value)}-{sequence}.json"
    )


class OCIStorageService:
    def __init__(
        self,
        client: ObjectStorageClientProtocol,
        *,
        namespace: str,
        bucket_name: str,
    ) -> None:
        self._client = client
        self._namespace = namespace
        self._bucket_name = bucket_name

    def upload_original(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> AlmacenamientoOCISchema:
        object_name = build_original_object_name(filename, content)
        return self._upload(
            object_name=object_name,
            content=content,
            content_type=content_type or "application/octet-stream",
        )

    def persist_generated_package(
            self,
            *,
            payload: InputSchema,
            response: OutputSchema,
    ) -> OutputSchema:
        object_name = build_generated_object_name(payload)
        completed_storage = AlmacenamientoOCISchema(
            documento_id=payload.documento_id,  # <--- Agregado aquí
            bucket=self._bucket_name,
            objeto_id=object_name,
            status_upload="completado",
        )
        package = response.model_copy(update={"almacenamiento_oci": completed_storage})
        upload = self._upload(
            object_name=object_name,
            content=package.model_dump_json().encode("utf-8"),
            content_type="application/json",
            documento_id=payload.documento_id,  # <--- Pasado a _upload
        )
        return response.model_copy(update={"almacenamiento_oci": upload})

    def _upload(
            self,
            *,
            object_name: str,
            content: bytes,
            content_type: str,
            documento_id: str | None = None,
    ) -> AlmacenamientoOCISchema:
        try:
            self._client.put_object(
                namespace_name=self._namespace,
                bucket_name=self._bucket_name,
                object_name=object_name,
                put_object_body=content,
                content_type=content_type,
            )
            status_upload = "completado"
        except Exception as error:
            logger.error(
                "Falló la carga del objeto '%s' en OCI Object Storage (%s) [request_id=%s].",
                object_name,
                type(error).__name__,
                get_request_id(),
            )
            status_upload = "error"  

        return AlmacenamientoOCISchema(
            documento_id=documento_id,
            bucket=self._bucket_name,
            objeto_id=object_name,
            status_upload=status_upload,
        )


def _build_api_key_config(app_settings: Settings) -> dict[str, str]:
    environment_values = {
        "OCI_USER_OCID": ("user", app_settings.OCI_USER_OCID),
        "OCI_TENANCY_OCID": ("tenancy", app_settings.OCI_TENANCY_OCID),
        "OCI_FINGERPRINT": ("fingerprint", app_settings.OCI_FINGERPRINT),
        "OCI_KEY_FILE": ("key_file", app_settings.OCI_KEY_FILE),
        "OCI_REGION": ("region", app_settings.OCI_REGION),
    }
    missing = [name for name, (_, value) in environment_values.items() if not value]
    if missing:
        raise ValueError(
            "Faltan variables de entorno para OCI_AUTH_MODE=api_key: "
            + ", ".join(sorted(missing))
        )
    config = {config_name: value for config_name, value in environment_values.values()}
    if app_settings.OCI_KEY_PASSPHRASE is not None:
        config["pass_phrase"] = app_settings.OCI_KEY_PASSPHRASE.get_secret_value()
    return config


def build_object_storage_client(app_settings: Settings) -> ObjectStorageClientProtocol:
    if app_settings.OCI_AUTH_MODE == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return oci.object_storage.ObjectStorageClient(config={}, signer=signer)

    config = _build_api_key_config(app_settings)
    oci.config.validate_config(config)
    return oci.object_storage.ObjectStorageClient(config)


def get_oci_storage_service() -> OCIStorageService:
    if not settings.OCI_NAMESPACE:
        raise ValueError("OCI_NAMESPACE debe configurarse mediante una variable de entorno.")

    return OCIStorageService(
        build_object_storage_client(settings),
        namespace=settings.OCI_NAMESPACE,
        bucket_name=settings.OCI_BUCKET_NAME,
    )


def get_oci_storage_service_factory() -> Callable[[], OCIStorageService]:
    """Inyecta una fábrica para posponer la autenticación hasta que sea necesaria."""
    return get_oci_storage_service
