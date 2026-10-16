from typing import Literal, Union

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

from app.schemas.base import PublicSchema
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


class MetadatosSchema(PublicSchema):
    perfil_aplicado: PerfilDestinatario

    formato_generado: FormatoSalida

    tiempo_estimado_estudio_minutos: StrictInt = Field(
        ...,
        ge=0,
    )

    conceptos_clave: list[StrictStr] = Field(
        ...,
        min_length=1,
    )
    prerrequisitos: list[StrictStr] = Field(default_factory=list)


class ContenidoAdaptadoSchema(PublicSchema):
    titulo: StrictStr = Field(
        ...,
        min_length=1,
    )

    introduccion_contextualizada: StrictStr = Field(
        ...,
        min_length=1,
    )

    items: list[ContenidoItem] = Field(
        ...,
        min_length=1,
    )


class EvaluacionCalidadSchema(PublicSchema):
    anclaje_fuente_score: StrictFloat = Field(
        ...,
        ge=0,
        le=1,
    )

    claridad_pedagogica: Literal["Alta", "Media", "Baja"]

    observaciones: StrictStr


class AlmacenamientoOCISchema(PublicSchema):
    bucket: StrictStr = Field(
        ...,
        min_length=1,
    )

    objeto_id: StrictStr = Field(
        ...,
        min_length=1,
    )

    status_upload: Literal["completado", "error"]


class OutputSchema(PublicSchema):
    status: Literal["exito", "error"]

    metadatos: MetadatosSchema

    contenido_adaptado: ContenidoAdaptadoSchema

    evaluacion_calidad: EvaluacionCalidadSchema

    almacenamiento_oci: AlmacenamientoOCISchema

    @model_validator(mode="after")
    def validar_items_del_formato(self) -> "OutputSchema":
        tipos_por_formato = {
            FormatoSalida.TUTORIAL: TutorialItem,
            FormatoSalida.FLASHCARDS: FlashcardItem,
            FormatoSalida.QUIZ: QuizItem,
            FormatoSalida.RESUMEN_EJECUTIVO: ResumenItem,
            FormatoSalida.GUION_CLASE: GuionItem,
        }
        formato = self.metadatos.formato_generado
        tipo_esperado = tipos_por_formato[formato]
        for indice, item in enumerate(self.contenido_adaptado.items):
            if not isinstance(item, tipo_esperado):
                raise ValueError(
                    f"contenido_adaptado.items[{indice}] no corresponde "
                    f"al formato '{formato.value}'"
                )
        return self


class ErrorSchema(PublicSchema):
    codigo: StrictStr = Field(
        ...,
        min_length=1,
        description="Código identificador del error",
    )

    mensaje: StrictStr = Field(
        ...,
        min_length=1,
        description="Descripción del error",
    )
