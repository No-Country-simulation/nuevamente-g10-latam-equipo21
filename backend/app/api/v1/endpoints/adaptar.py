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
    "documento_contenido": (
        "La Virtual Cloud Network (VCN) es una red privada y personalizable en OCI. "
        "Permite definir subredes y reglas de seguridad para controlar el tráfico. "
        "Cada subred pertenece a una VCN y utiliza un rango de direcciones IP."
    ),
    "perfil_destinatario": "Principiante",
    "formato_salida": "Flashcards",
    "nicho_sector": "General",
    "nivel_detalle": "Didactico",
}

# Valores ilustrativos: lo que importa es la forma, y un test verifica que
# cumple el contrato (OutputSchema) para que no se desactualice.
_EJEMPLO_RESPUESTA_200 = {
    "status": "exito",
    "metadatos": {
        "perfil_aplicado": "Principiante",
        "formato_generado": "Flashcards",
        "tiempo_estimado_estudio_minutos": 5,
        "conceptos_clave": ["VCN", "Subredes", "Internet Gateway"],
        "prerrequisitos": [],
    },
    "contenido_adaptado": {
        "titulo": "Dominando Redes en la Nube desde Cero",
        "introduccion_contextualizada": "Una VCN es tu red privada dentro de OCI...",
        "items": [
            {
                "frente": "¿Qué es una VCN?",
                "dorso": "Una red privada y personalizable en Oracle Cloud Infrastructure.",
                "pista_didactica": "Pensá en tu propia red de oficina, pero en la nube.",
            }
        ],
    },
    "evaluacion_calidad": {
        "anclaje_fuente_score": 0.9,
        "claridad_pedagogica": "Alta",
        "observaciones": "Contenido respaldado por el documento fuente.",
        "umbral_fidelidad": 0.7,
        "requiere_revision": False,
        "afirmaciones_no_respaldadas": [],
    },
    "almacenamiento_oci": {
        "bucket": "nuevamente-contenidos-educativos",
        "objeto_id": "contenido-ejemplo.json",
        "status_upload": "completado",
    },
}


@router.post(
    "/adaptar-contenido",
    response_model=OutputSchema,
    responses={
        200: {
            "description": "Paquete generado. Consultar evaluacion_calidad para advertencias y almacenamiento_oci para el estado de persistencia.",
            "content": {"application/json": {"example": _EJEMPLO_RESPUESTA_200}},
        },
        422: {
            "description": (
                "Entrada inválida, contexto no encontrado o documento demasiado corto. "
                "DOCUMENTO_INSUFICIENTE indica que no alcanza DOCUMENT_MIN_WORDS; "
                "no se ejecuta la generación."
            ),
            "content": _EJEMPLO_ERROR("ENTRADA_INVALIDA", "Campo 'perfil_destinatario': Input should be 'Principiante', ..."),
        },
        502: {
            "description": (
                "Falla del LLM, vector store o autenticación con OCI Object Storage."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "llm_no_disponible": {
                            "summary": "Falla del LLM",
                            "value": {
                                "status": "error",
                                "error": {
                                    "codigo": "LLM_NO_DISPONIBLE",
                                    "mensaje": (
                                        "No se pudo generar el contenido en este momento. "
                                        "Intenta nuevamente."
                                    ),
                                },
                            },
                        },
                        "oci_autenticacion_error": {
                            "summary": "Falla de autenticación OCI",
                            "value": {
                                "status": "error",
                                "error": {
                                    "codigo": "OCI_AUTENTICACION_ERROR",
                                    "mensaje": (
                                        "No fue posible autenticarse con OCI Object Storage. "
                                        "Verifica la configuración de credenciales e intenta nuevamente."
                                    ),
                                },
                            },
                        },
                    }
                }
            },
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
