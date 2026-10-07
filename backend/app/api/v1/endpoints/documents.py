import logging
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from app.core.errors import OCIAuthenticationError

from app.services.document_ingestion import (
    DocumentExtractionError,
    extract_document,
)
from app.services.oci_storage_service import (
    OCIStorageService,
    get_oci_storage_service_factory,
)


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
    """Recibe un documento desde el frontend y retorna le texto extraído y metadatos."""
    suffix = Path(file.filename or "").suffix
    temporary_path = None

    try:
        content = await file.read()
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)

        document = extract_document(temporary_path)
        metadata = replace(
            document.metadata,
            filename=file.filename or temporary_path.name,
        )

        def persist_original() -> None:
            storage_service_factory().upload_original(
                filename=metadata.filename,
                content=content,
                content_type=file.content_type,
            )

        try:
            await run_in_threadpool(persist_original)

        except OCIAuthenticationError:
            raise

        except Exception as error:
            logger.warning(
                "No se pudo persistir el documento original en OCI (%s); se continúa.",
                type(error).__name__,
            )
        return {
            "text": document.text,
            "metadata": asdict(metadata),
        }
    except DocumentExtractionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
