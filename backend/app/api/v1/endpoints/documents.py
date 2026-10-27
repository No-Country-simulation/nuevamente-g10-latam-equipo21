import logging
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import (
    DocumentoInvalidoError,
    DocumentoNoSoportadoError,
    DocumentoSinTextoError,
    OCIAuthenticationError,
)

from app.services.diagram_interpretation_service import (
    DiagramInterpretationError,
    DiagramInterpretationService,
    get_diagram_interpretation_service,
)
from app.services.document_ingestion import (
    DocumentExtractionError,
    EmptyPdfTextError,
    ExtractedImage,
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


def _is_diagram_candidate(image: ExtractedImage) -> bool:
    """Conserva imágenes sin dimensiones conocidas y descarta íconos pequeños."""
    if image.width is None or image.height is None:
        return True
    return image.width * image.height >= settings.DIAGRAM_MIN_IMAGE_AREA_PIXELS


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
    """Recibe un documento desde el frontend y retorna el texto extraído, metadatos y estado de persistencia."""
    suffix = Path(file.filename or "").suffix
    temporary_path = None

    try:
        content = await file.read()
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)

        document = extract_document(
            temporary_path,
            original_filename=file.filename or "documento",
        )
        documento_id = documento_id_desde_contenido(document.text)
        metadata = replace(
            document.metadata,
            filename=file.filename or temporary_path.name,
        )

        diagram_images = tuple(
            image for image in document.images if _is_diagram_candidate(image)
        )
        skipped_small_images = len(document.images) - len(diagram_images)
        if skipped_small_images:
            logger.info(
                "Se omitieron %d imágenes pequeñas antes del análisis multimodal.",
                skipped_small_images,
            )

        image_count = len(diagram_images)
        if image_count > settings.DIAGRAM_MAX_IMAGES_PER_DOCUMENT:
            raise DocumentoInvalidoError(
                "El PDF contiene "
                f"{image_count} imágenes; el máximo permitido es "
                f"{settings.DIAGRAM_MAX_IMAGES_PER_DOCUMENT}."
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

        diagrams = []
        for image in diagram_images:
            try:
                interpreted = await run_in_threadpool(
                    diagram_service.interpret,
                    image,
                )
                diagrams.append(asdict(interpreted))
            except DiagramInterpretationError as error:
                logger.warning(
                    "No se pudo interpretar la imagen página=%d índice=%d (%s); se continúa.",
                    image.page_number,
                    image.image_index,
                    type(error).__name__,
                )

        response = {
            "documento_id": documento_id,
            "objeto_id": objeto_id,
            "status_upload": status_upload,
            "text": document.text,
            "pages": [asdict(p) for p in getattr(document, "pages", [])],
            "metadata": asdict(metadata),
        }
        if diagrams:
            response["diagramas"] = diagrams
        return response
    except UnsupportedDocumentFormatError as error:
        raise DocumentoNoSoportadoError(str(error)) from error
    except EmptyPdfTextError as error:
        raise DocumentoSinTextoError(str(error)) from error
    except DocumentExtractionError as error:
        raise DocumentoInvalidoError(str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
