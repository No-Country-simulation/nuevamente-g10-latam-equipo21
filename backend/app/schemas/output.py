from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.schemas.content import (
    FlashcardsContent,
    GuionContent,
    QuizContent,
    ResumenContent,
    TutorialContent,
)
from app.schemas.enums import (
    FormatoSalida,
    NichoSector,
    NivelDetalle,
    PerfilDestinatario,
)


ContenidoAdaptado = Annotated[
    Union[
        TutorialContent,
        FlashcardsContent,
        QuizContent,
        ResumenContent,
        GuionContent,
    ],
    Field(discriminator="formato_salida"),
]


class MetadatosSchema(BaseModel):
    titulo_original: str = Field(
        ...,
        min_length=3,
        description="Título del documento técnico original",
    )
    perfil_destinatario: PerfilDestinatario
    formato_salida: FormatoSalida
    nicho_sector: NichoSector
    nivel_detalle: NivelDetalle


class EvaluacionCalidadSchema(BaseModel):
    puntaje: float = Field(
        ...,
        ge=0,
        le=100,
        description="Puntaje de calidad del contenido entre 0 y 100",
    )
    observaciones: list[str] = Field(
        default_factory=list,
        description="Observaciones obtenidas durante la evaluación de calidad",
    )


class AlmacenamientoOCISchema(BaseModel):
    guardado: bool = Field(
        ...,
        description="Indica si el resultado fue almacenado correctamente en OCI",
    )
    referencia: str | None = Field(
        default=None,
        description="Referencia o identificador del contenido almacenado",
    )


class OutputSchema(BaseModel):
    status: Literal["success"] = "success"
    metadatos: MetadatosSchema
    contenido_adaptado: ContenidoAdaptado
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
