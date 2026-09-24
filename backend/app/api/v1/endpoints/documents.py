from dataclasses import asdict, replace
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.services.document_ingestion import (
    DocumentExtractionError,
    extract_document,
)


router = APIRouter()


@router.post(
    "/documents/extract",
    status_code=status.HTTP_200_OK,
    summary="Extrae texto normalizado de un documento",
)
async def extract_document_endpoint(file: UploadFile):
    """Recibe un documento desde el frontend y retorna le texto extraído y metadatos."""
    suffix = Path(file.filename or "").suffix
    temporary_path = None

    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(await file.read())

        document = extract_document(temporary_path)
        metadata = replace(
            document.metadata,
            filename=file.filename or temporary_path.name,
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