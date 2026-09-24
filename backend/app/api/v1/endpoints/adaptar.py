from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.errors import ErrorResponse
from app.schemas.request import AdaptarContenidoRequest
from app.schemas.response import AdaptarContenidoResponse
from app.services.mock_adaptacion_service import construir_respuesta_mock

router = APIRouter()


@router.post(
    "/adaptar-contenido",
    response_model=AdaptarContenidoResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Entrada inválida contra el contrato."},
        501: {"description": "Mock deshabilitado y endpoint real (NM-12) aún no implementado."},
    },
    summary="Adapta un documento técnico a un formato educativo (mock — NM-18)",
)
async def adaptar_contenido(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
    if not settings.USE_MOCK_LLM:
        # Punto de extensión para NM-12: acá se llamará al servicio real
        # (RAG + LLM) en lugar de devolver este error.
        raise HTTPException(
            status_code=501,
            detail=(
                "USE_MOCK_LLM=false y el endpoint real todavía no está implementado (NM-12)."
            ),
        )

    return construir_respuesta_mock(payload)
