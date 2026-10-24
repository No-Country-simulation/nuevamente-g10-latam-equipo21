import logging
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from app.core.errors import (
    DocumentoInvalidoError,
    DocumentoNoSoportadoError,
    DocumentoSinTextoError,
    OCIAuthenticationError,
)

from app.services.document_ingestion import (
    DocumentExtractionError,
    EmptyPdfTextError,
    UnsupportedDocumentFormatError,
    extract_document,
)
from app.services.oci_storage_service import (
    OCIStorageService,
    get_oci_storage_service_factory,
)
from app.services.document_identity import documento_id_desde_contenido

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/documents/extract",
    status_code=status.HTTP_200_OK,
    summary="Extrae texto normalizado de un documento",
)
async def extract_document_endpoint(
    file: UploadFile,
    storage_service_factory: Annotated[
        Callable[[], OCIStorageService],
        Depends(get_oci_storage_service_factory),
    ],
):
    """Recibe un documento desde el frontend y retorna el texto extraído, metadatos y estado de persistencia."""
    suffix = Path(file.filename or "").suffix
    temporary_path = None

    try:
        content = await file.read()
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)

        document = extract_document(temporary_path)
        documento_id = documento_id_desde_contenido(document.text)
        metadata = replace(
            document.metadata,
            filename=file.filename or temporary_path.name,
        )

        objeto_id = None
        status_upload = "error"

        def persist_original():
            return storage_service_factory().upload_original(
                filename=metadata.filename,
                content=content,
                content_type=file.content_type,
            )

        try:
            almacenamiento_original = await run_in_threadpool(persist_original)
            objeto_id = almacenamiento_original.objeto_id
            status_upload = almacenamiento_original.status_upload
        except OCIAuthenticationError:
            raise
        except Exception as error:
            status_upload = "error"
            logger.warning(
                "No se pudo persistir el documento original en OCI (%s); se continúa.",
                type(error).__name__,
            )

        return {
            "documento_id": documento_id,
            "objeto_id": objeto_id,
            "status_upload": status_upload,
            "text": document.text,
            "pages": [asdict(p) for p in getattr(document, "pages", [])],
            "metadata": asdict(metadata),
        }

    except UnsupportedDocumentFormatError as error:
        raise DocumentoNoSoportadoError(str(error)) from error
    except EmptyPdfTextError as error:
        raise DocumentoSinTextoError(str(error)) from error
    except DocumentExtractionError as error:
        raise DocumentoInvalidoError(str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)