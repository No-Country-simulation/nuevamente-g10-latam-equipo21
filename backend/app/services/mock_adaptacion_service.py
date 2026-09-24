"""
Respuestas mock de POST /adaptar-contenido, una por cada formato_salida.

Estas respuestas son fijas y válidas contra los modelos Pydantic de
app.schemas.response — no se genera contenido dinámicamente, salvo el
título y el perfil, que se toman del request para que el mock se sienta
coherente con lo que pidió quien está probando el frontend.

Vive en app/services/ (y no en app/api/) siguiendo la separación de NM-03:
la capa de API solo orquesta, la lógica de negocio va en servicios.
"""

import uuid

from app.core.config import settings
from app.schemas.enums import FormatoSalida
from app.schemas.request import AdaptarContenidoRequest
from app.schemas.response import (
    AdaptarContenidoResponse,
    AlmacenamientoOci,
    ContenidoAdaptado,
    EvaluacionCalidad,
    FlashcardItem,
    GuionItem,
    Metadatos,
    QuizItem,
    ResumenItem,
    TutorialItem,
)

# Se toma del Settings centralizado (NM-03), no hardcodeado, para que quede
# consistente con OCI_BUCKET_NAME cuando NM-11/NM-02 lo usen de verdad.
BUCKET_MOCK = settings.OCI_BUCKET_NAME


def _base_metadatos(payload: AdaptarContenidoRequest, minutos: int, conceptos: list[str]) -> Metadatos:
    return Metadatos(
        perfil_aplicado=payload.perfil_destinatario.value,
        formato_generado=payload.formato_salida.value,
        tiempo_estimado_estudio_minutos=minutos,
        conceptos_clave=conceptos,
    )


def _base_evaluacion() -> EvaluacionCalidad:
    return EvaluacionCalidad(
        anclaje_fuente_score=0.95,
        claridad_pedagogica="Alta",
        observaciones="Respuesta MOCK (NM-18) — no proviene de la pipeline RAG real.",
    )


def _base_almacenamiento() -> AlmacenamientoOci:
    return AlmacenamientoOci(
        bucket=BUCKET_MOCK,
        objeto_id=f"mock/{uuid.uuid4()}.json",
        status_upload="completado",
    )


def _mock_flashcards(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
    items = [
        FlashcardItem(
            frente="¿Qué es una VCN?",
            dorso="Una red privada virtual configurable dentro de OCI.",
            pista_didactica="Pensala como tu propia red aislada en la nube.",
        ),
        FlashcardItem(
            frente="¿Para qué sirve un Internet Gateway?",
            dorso="Permite el tráfico entre la VCN e internet.",
            pista_didactica="Es la 'puerta' de salida/entrada pública.",
        ),
    ]
    return AdaptarContenidoResponse(
        metadatos=_base_metadatos(payload, minutos=5, conceptos=["VCN", "Subredes", "Internet Gateway"]),
        contenido_adaptado=ContenidoAdaptado(
            titulo=f"Dominando '{payload.documento_titulo}' desde cero",
            introduccion_contextualizada="Estas flashcards resumen los conceptos clave del documento (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_quiz(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
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
    return AdaptarContenidoResponse(
        metadatos=_base_metadatos(payload, minutos=8, conceptos=["VCN", "Security Lists"]),
        contenido_adaptado=ContenidoAdaptado(
            titulo=f"Quiz: {payload.documento_titulo}",
            introduccion_contextualizada="Responde estas preguntas para validar lo aprendido (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_tutorial(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
    items = [
        TutorialItem(
            paso_numero=1,
            titulo_paso="Crear la VCN",
            contenido="Definí el CIDR block y la región de la VCN (MOCK).",
            codigo_ejemplo="oci network vcn create --cidr-block 10.0.0.0/16",
        ),
        TutorialItem(
            paso_numero=2,
            titulo_paso="Agregar subredes",
            contenido="Creá al menos una subred pública y una privada (MOCK).",
            codigo_ejemplo=None,
        ),
    ]
    return AdaptarContenidoResponse(
        metadatos=_base_metadatos(payload, minutos=15, conceptos=["VCN", "Subredes", "CIDR"]),
        contenido_adaptado=ContenidoAdaptado(
            titulo=f"Tutorial paso a paso: {payload.documento_titulo}",
            introduccion_contextualizada="Guía práctica orientada a nicho técnico (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_resumen_ejecutivo(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
    items = [
        ResumenItem(
            punto_clave="Aislamiento de red como base de seguridad",
            descripcion="La VCN separa el tráfico interno del tráfico público (MOCK).",
            impacto_negocio="Reduce riesgo de exposición de datos sensibles.",
        ),
    ]
    return AdaptarContenidoResponse(
        metadatos=_base_metadatos(payload, minutos=3, conceptos=["VCN", "Seguridad"]),
        contenido_adaptado=ContenidoAdaptado(
            titulo=f"Resumen ejecutivo: {payload.documento_titulo}",
            introduccion_contextualizada="Lectura de 3 minutos para perfiles no técnicos (MOCK).",
            items=items,
        ),
        evaluacion_calidad=_base_evaluacion(),
        almacenamiento_oci=_base_almacenamiento(),
    )


def _mock_guion_clase(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
    items = [
        GuionItem(
            seccion="Introducción",
            tiempo_estimado_minutos=2,
            narracion="Hoy vamos a entender qué es una VCN y por qué importa (MOCK).",
            notas_visuales="Mostrar diagrama de red con VCN al centro.",
        ),
    ]
    return AdaptarContenidoResponse(
        metadatos=_base_metadatos(payload, minutos=10, conceptos=["VCN"]),
        contenido_adaptado=ContenidoAdaptado(
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


def construir_respuesta_mock(payload: AdaptarContenidoRequest) -> AdaptarContenidoResponse:
    """Selecciona y arma la respuesta mock según formato_salida (criterio de NM-18)."""
    factory = _FACTORIES[payload.formato_salida]
    return factory(payload)
