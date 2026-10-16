"""
Respuestas mock de POST /adaptar-contenido, una por cada formato_salida.

Ajustado tras confirmar el contrato definitivo de NM-07 (app.schemas.input /
app.schemas.output / app.schemas.content), que en la práctica coincide casi
en su totalidad con el contrato original de ARCHITECTURE.md (NM-01):
Metadatos → perfil_aplicado/formato_generado/tiempo_estimado_estudio_minutos/
conceptos_clave, EvaluacionCalidad → anclaje_fuente_score (0-1) +
claridad_pedagogica + observaciones, AlmacenamientoOci → bucket/objeto_id/
status_upload, y ContenidoAdaptado con titulo + introduccion_contextualizada
+ items.

Nota: app.schemas.output.ContenidoAdaptadoSchema arma `items` como una unión
simple de los *Item (FlashcardItem, QuizItem, TutorialItem, ResumenItem,
GuionItem). OutputSchema valida después que cada item coincida con
`formato_generado`, sin agregar un discriminador al contrato público.
Por eso acá se instancia ContenidoAdaptadoSchema directamente.

El campo `tipo_item` (propuesto originalmente en NM-18 como discriminador
por item) no forma parte del contrato final.

Vive en app/services/ (y no en app/api/) siguiendo la separación de NM-03:
la capa de API solo orquesta, la lógica de negocio va en servicios.
"""


from app.core.config import settings
from app.schemas.content import (
    FlashcardItem,
    GuionItem,
    QuizItem,
    ResumenItem,
    TutorialItem,
)
from app.schemas.enums import FormatoSalida
from app.schemas.input import InputSchema
from app.schemas.output import (
    AlmacenamientoOCISchema,
    ContenidoAdaptadoSchema,
    EvaluacionCalidadSchema,
    MetadatosSchema,
    OutputSchema,
)

# Se toma del Settings centralizado (NM-03), no hardcodeado, para que quede
# consistente con OCI_BUCKET_NAME cuando NM-11/NM-02 lo usen de verdad.
BUCKET_MOCK = settings.OCI_BUCKET_NAME

# Identificador propio del mock. Es distinto de "no-persistido" (el valor del flujo real)
# para que una respuesta simulada se pueda reconocer a simple vista (NM-20).
OBJETO_ID_MOCK = "mock-no-persistido"


def _base_metadatos(payload: InputSchema, minutos: int, conceptos: list[str]) -> MetadatosSchema:
    return MetadatosSchema(
        perfil_aplicado=payload.perfil_destinatario,
        formato_generado=payload.formato_salida,
        tiempo_estimado_estudio_minutos=minutos,
        conceptos_clave=conceptos,
    )


def _base_evaluacion() -> EvaluacionCalidadSchema:
    return EvaluacionCalidadSchema(
        anclaje_fuente_score=0.95,
        claridad_pedagogica="Alta",
        observaciones="Respuesta MOCK (NM-18) — no proviene de la pipeline RAG real.",
    )


def _base_almacenamiento() -> AlmacenamientoOCISchema:
    # El mock no sube nada a OCI. status_upload="error" indica que no hubo subida
    # y objeto_id="mock-no-persistido" identifica la respuesta como simulada.
    # Reportar "completado" sería un éxito falso (NM-20).
    return AlmacenamientoOCISchema(
        bucket=BUCKET_MOCK,
        objeto_id=OBJETO_ID_MOCK,
        status_upload="error",
    )

def _mock_flashcards(payload: InputSchema) -> OutputSchema:
    items = [
        FlashcardItem(
            frente="¿Qué es una VCN?",
            dorso="Una red privada virtual configurable dentro de OCI.",
            pista_didactica="Puede pensarse como una red aislada propia dentro de la nube.",
        ),
        FlashcardItem(
            frente="¿Para qué sirve un Internet Gateway?",
            dorso="Permite el tráfico entre la VCN e internet.",
            pista_didactica="Es la 'puerta' de salida y entrada pública.",
        ),
    ]
    return OutputSchema(
        status="exito",
        metadatos=_base_metadatos(payload, minutos=5, conceptos=["VCN", "Subredes", "Internet Gateway"]),
        contenido_adaptado=ContenidoAdaptadoSchema(
            titulo=f"Dominando '{payload.documento_titulo}' desde cero",
            introduccion_contextualizada="Estas flashcards resumen los conceptos clave del documento (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_quiz(payload: InputSchema) -> OutputSchema:
    items = [
        QuizItem(
            pregunta="¿Cuál es el propósito principal de una VCN?",
            opciones=[
                "Almacenar archivos",
                "Aislar y controlar el tráfico de red en la nube",
                "Ejecutar contenedores",
                "Facturar el consumo de cómputo",
            ],
            respuesta_correcta="Aislar y controlar el tráfico de red en la nube",
            justificacion="La VCN define el espacio de red privado del tenant (MOCK).",
        ),
    ]
    return OutputSchema(
        status="exito",
        metadatos=_base_metadatos(payload, minutos=8, conceptos=["VCN", "Security Lists"]),
        contenido_adaptado=ContenidoAdaptadoSchema(
            titulo=f"Quiz: {payload.documento_titulo}",
            introduccion_contextualizada="Responde estas preguntas para validar lo aprendido (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_tutorial(payload: InputSchema) -> OutputSchema:
    items = [
        TutorialItem(
            paso_numero=1,
            titulo_paso="Crear la VCN",
            contenido="Definir el CIDR block y la región de la VCN (MOCK).",
            codigo_ejemplo="oci network vcn create --cidr-block 10.0.0.0/16",
        ),
        TutorialItem(
            paso_numero=2,
            titulo_paso="Agregar subredes",
            contenido="Crear al menos una subred pública y una privada (MOCK).",
            codigo_ejemplo=None,
        ),
    ]
    return OutputSchema(
        status="exito",
        metadatos=_base_metadatos(payload, minutos=15, conceptos=["VCN", "Subredes", "CIDR"]),
        contenido_adaptado=ContenidoAdaptadoSchema(
            titulo=f"Tutorial paso a paso: {payload.documento_titulo}",
            introduccion_contextualizada="Guía práctica orientada a nicho técnico (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_resumen_ejecutivo(payload: InputSchema) -> OutputSchema:
    items = [
        ResumenItem(
            punto_clave="Aislamiento de red como base de seguridad",
            descripcion="La VCN separa el tráfico interno del tráfico público (MOCK).",
            impacto_negocio="Reduce el riesgo de exposición de datos sensibles.",
        ),
    ]
    return OutputSchema(
        status="exito",
        metadatos=_base_metadatos(payload, minutos=3, conceptos=["VCN", "Seguridad"]),
        contenido_adaptado=ContenidoAdaptadoSchema(
            titulo=f"Resumen ejecutivo: {payload.documento_titulo}",
            introduccion_contextualizada="Lectura de 3 minutos para perfiles no técnicos (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_guion_clase(payload: InputSchema) -> OutputSchema:
    items = [
        GuionItem(
            seccion="Introducción",
            tiempo_estimado_minutos=2,
            narracion="Hoy vamos a entender qué es una VCN y por qué importa (MOCK).",
            notas_visuales="Mostrar diagrama de red con la VCN al centro.",
        ),
    ]
    return OutputSchema(
        status="exito",
        metadatos=_base_metadatos(payload, minutos=10, conceptos=["VCN"]),
        contenido_adaptado=ContenidoAdaptadoSchema(
            titulo=f"Guion de clase: {payload.documento_titulo}",
            introduccion_contextualizada="Guion narrado para una clase corta (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


_FACTORIES = {
    FormatoSalida.FLASHCARDS: _mock_flashcards,
    FormatoSalida.QUIZ: _mock_quiz,
    FormatoSalida.TUTORIAL: _mock_tutorial,
    FormatoSalida.RESUMEN_EJECUTIVO: _mock_resumen_ejecutivo,
    FormatoSalida.GUION_CLASE: _mock_guion_clase,
}


def construir_respuesta_mock(payload: InputSchema) -> OutputSchema:
    """Selecciona y arma la respuesta mock según formato_salida (criterio de NM-18)."""
    factory = _FACTORIES[payload.formato_salida]
    return factory(payload)
