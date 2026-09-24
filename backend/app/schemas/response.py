from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Items polimórficos de contenido_adaptado.items (docs/ARCHITECTURE.md §5)
#
# Nota de implementación: ARCHITECTURE.md no define un campo discriminador
# explícito dentro de cada item (la variante se infiere de `formato_salida`
# a nivel de la respuesta completa). Para que Pydantic pueda validar
# estrictamente una lista polimórfica, se agrega aquí `tipo_item` como
# discriminador técnico. Si NM-07 define los esquemas definitivos de otra
# forma, este archivo debe alinearse a esa decisión.
# ---------------------------------------------------------------------------


class FlashcardItem(BaseModel):
    tipo_item: Literal["flashcard"] = "flashcard"
    frente: str
    dorso: str
    pista_didactica: str


class QuizItem(BaseModel):
    tipo_item: Literal["quiz"] = "quiz"
    pregunta: str
    opciones: List[str]
    respuesta_correcta: str
    justificacion: str


class TutorialItem(BaseModel):
    tipo_item: Literal["tutorial"] = "tutorial"
    paso_numero: int
    titulo_paso: str
    contenido: str
    codigo_ejemplo: Optional[str] = None


class ResumenItem(BaseModel):
    tipo_item: Literal["resumen"] = "resumen"
    punto_clave: str
    descripcion: str
    impacto_negocio: str


class GuionItem(BaseModel):
    tipo_item: Literal["guion"] = "guion"
    seccion: str
    tiempo_estimado_minutos: int
    narracion: str
    notas_visuales: str


ItemAdaptado = Union[FlashcardItem, QuizItem, TutorialItem, ResumenItem, GuionItem]


# ---------------------------------------------------------------------------
# Bloques comunes de la respuesta (docs/ARCHITECTURE.md §4)
# ---------------------------------------------------------------------------


class Metadatos(BaseModel):
    perfil_aplicado: str
    formato_generado: str
    tiempo_estimado_estudio_minutos: int
    conceptos_clave: List[str]


class ContenidoAdaptado(BaseModel):
    titulo: str
    introduccion_contextualizada: str
    items: List[ItemAdaptado]


class EvaluacionCalidad(BaseModel):
    anclaje_fuente_score: float = Field(..., ge=0, le=1)
    claridad_pedagogica: Literal["Alta", "Media", "Baja"]
    observaciones: str


class AlmacenamientoOci(BaseModel):
    bucket: str
    objeto_id: str
    status_upload: Literal["completado", "error"]


class AdaptarContenidoResponse(BaseModel):
    status: Literal["exito"] = "exito"
    metadatos: Metadatos
    contenido_adaptado: ContenidoAdaptado
    evaluacion_calidad: EvaluacionCalidad
    almacenamiento_oci: AlmacenamientoOci
