from fastapi import APIRouter, Depends

from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.dependencies import get_adaptacion_service

router = APIRouter()

_EJEMPLO_ERROR = lambda codigo, mensaje: {  # noqa: E731
    "application/json": {"example": {"status": "error", "error": {"codigo": codigo, "mensaje": mensaje}}}
}

_EJEMPLO_REQUEST = {
    "documento_titulo": "Introduccion a la Arquitectura de Redes VCN en OCI",
    "documento_contenido": "La Virtual Cloud Network (VCN) es una red privada y personalizable en OCI...",
    "perfil_destinatario": "Principiante",
    "formato_salida": "Flashcards",
    "nicho_sector": "General",
    "nivel_detalle": "Didactico",
}


@router.post(
    "/adaptar-contenido",
    response_model=OutputSchema,
    responses={
        422: {
            "description": "Entrada inválida (campo faltante o valor fuera de enum; el mensaje lista los valores válidos).",
            "content": _EJEMPLO_ERROR("ENTRADA_INVALIDA", "Campo 'perfil_destinatario': Input should be 'Principiante', ..."),
        },
        502: {
            "description": "Falla del LLM o del vector store.",
            "content": _EJEMPLO_ERROR("LLM_NO_DISPONIBLE", "No se pudo generar el contenido en este momento. Intenta nuevamente."),
        },
        501: {
            "description": "Pipeline real aún no cableada en este entorno (USE_MOCK_LLM=false).",
            "content": _EJEMPLO_ERROR("PIPELINE_NO_CONFIGURADA", "La pipeline de adaptación aún no está disponible en este entorno."),
        },
    },
    summary="Adapta un documento técnico a un formato educativo",
    openapi_extra={"requestBody": {"content": {"application/json": {"example": _EJEMPLO_REQUEST}}}},
)
def adaptar_contenido(
    payload: InputSchema,
    service=Depends(get_adaptacion_service),
) -> OutputSchema:
    # `def` (no async): el pipeline es bloqueante (LLM, Chroma, OCI); FastAPI lo
    # corre en threadpool y no bloquea el event loop.
    return service.adaptar(payload)
