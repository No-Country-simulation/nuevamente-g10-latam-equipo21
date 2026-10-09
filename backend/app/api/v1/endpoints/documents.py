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
from app.services.diagram_interpretation_service import (
    DiagramInterpretationService,
    get_diagram_interpretation_service,
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
    diagram_service: Annotated[
        DiagramInterpretationService,
        Depends(get_diagram_interpretation_service),
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
        diagramas = []

        for image in document.images:
            interpreted = await run_in_threadpool(
                diagram_service.interpret,
                image,
            )

            diagramas.append(
                {
                    "description": interpreted.description,
                    "page_number": interpreted.page_number,
                    "image_index": interpreted.image_index,
                    "image_name": interpreted.image_name,
                }
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
        response = {
            "text": document.text,
            "metadata": asdict(metadata),
            "pages": [asdict(pagina) for pagina in document.pages],
        }

        if diagramas:
            response["diagramas"] = diagramas

        return response
    except DocumentExtractionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
