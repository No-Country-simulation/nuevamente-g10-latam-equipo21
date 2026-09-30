from typing import Literal, Union

from pydantic import BaseModel, Field

from app.schemas.content import (
    FlashcardItem,
    GuionItem,
    QuizItem,
    ResumenItem,
    TutorialItem,
)
from app.schemas.enums import FormatoSalida, PerfilDestinatario


ContenidoItem = Union[
    TutorialItem,
    FlashcardItem,
    QuizItem,
    ResumenItem,
    GuionItem,
]


class MetadatosSchema(BaseModel):
    perfil_aplicado: PerfilDestinatario

    formato_generado: FormatoSalida

    tiempo_estimado_estudio_minutos: int = Field(
        ...,
        ge=0,
    )

    conceptos_clave: list[str] = Field(
        ...,
        min_length=1,
    )
    prerrequisitos: list[str] = Field(default_factory=list)


class ContenidoAdaptadoSchema(BaseModel):
    titulo: str = Field(
        ...,
        min_length=1,
    )

    introduccion_contextualizada: str = Field(
        ...,
        min_length=1,
    )

    items: list[ContenidoItem] = Field(
        ...,
        min_length=1,
    )


class EvaluacionCalidadSchema(BaseModel):
    anclaje_fuente_score: float = Field(
        ...,
        ge=0,
        le=1,
    )

    claridad_pedagogica: Literal["Alta", "Media", "Baja"]

    observaciones: str


class AlmacenamientoOCISchema(BaseModel):
    bucket: str = Field(
        ...,
        min_length=1,
    )

    objeto_id: str = Field(
        ...,
        min_length=1,
    )

    status_upload: Literal["completado", "error"]


class OutputSchema(BaseModel):
    status: Literal["exito", "error"]

    metadatos: MetadatosSchema

    contenido_adaptado: ContenidoAdaptadoSchema

    evaluacion_calidad: EvaluacionCalidadSchema

    almacenamiento_oci: AlmacenamientoOCISchema


class ErrorSchema(BaseModel):
    codigo: str = Field(
        ...,
        min_length=1,
        description="Código identificador del error",
    )

    mensaje: str = Field(
        ...,
        min_length=1,
        description="Descripción del error",
    )