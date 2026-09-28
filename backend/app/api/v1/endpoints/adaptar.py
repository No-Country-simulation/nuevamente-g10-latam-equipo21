from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.mock_adaptacion_service import construir_respuesta_mock

router = APIRouter()


@router.post(
    "/adaptar-contenido",
    response_model=OutputSchema,
    responses={
        422: {
            "description": (
                "Entrada inválida contra el contrato. El cuerpo real lo arma el "
                "exception_handler de RequestValidationError en app.main "
                "({\"status\": \"error\", \"error\": {\"codigo\", \"mensaje\"}}); "
                "ErrorSchema describe solo el bloque interno `error`."
            ),
        },
        501: {"description": "Mock deshabilitado y endpoint real (NM-12) aún no implementado."},
    },
    summary="Adapta un documento técnico a un formato educativo (mock — NM-18)",
)
async def adaptar_contenido(payload: InputSchema) -> OutputSchema:
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
