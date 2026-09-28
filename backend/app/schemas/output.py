from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from app.schemas.base import ContractSchema
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


TIPO_ITEM_POR_FORMATO: dict[FormatoSalida, type[BaseModel]] = {
    FormatoSalida.TUTORIAL: TutorialItem,
    FormatoSalida.FLASHCARDS: FlashcardItem,
    FormatoSalida.QUIZ: QuizItem,
    FormatoSalida.RESUMEN_EJECUTIVO: ResumenItem,
    FormatoSalida.GUION_CLASE: GuionItem,
}


def indices_items_incompatibles(
    formato_salida: FormatoSalida | str,
    items: list[ContenidoItem],
) -> list[int]:
    """Devuelve las posiciones cuyos items no corresponden al formato declarado."""
    formato = FormatoSalida(formato_salida)
    tipo_esperado = TIPO_ITEM_POR_FORMATO[formato]
    return [
        indice
        for indice, item in enumerate(items)
        if not isinstance(item, tipo_esperado)
    ]


class MetadatosSchema(ContractSchema):
    perfil_aplicado: PerfilDestinatario = Field(strict=False)

    formato_generado: FormatoSalida = Field(strict=False)

    tiempo_estimado_estudio_minutos: int = Field(
        ...,
        ge=0,
    )

    conceptos_clave: list[str] = Field(
        ...,
        min_length=1,
    )


class ContenidoAdaptadoSchema(ContractSchema):
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


class EvaluacionCalidadSchema(ContractSchema):
    anclaje_fuente_score: float = Field(
        ...,
        ge=0,
        le=1,
    )

    claridad_pedagogica: Literal["Alta", "Media", "Baja"]

    observaciones: str


class AlmacenamientoOCISchema(ContractSchema):
    bucket: str = Field(
        ...,
        min_length=1,
    )

    objeto_id: str = Field(
        ...,
        min_length=1,
    )

    status_upload: Literal["completado", "error"]


class ErrorSchema(ContractSchema):
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


class OutputExitoSchema(ContractSchema):
    status: Literal["exito"]

    metadatos: MetadatosSchema

    contenido_adaptado: ContenidoAdaptadoSchema

    evaluacion_calidad: EvaluacionCalidadSchema

    almacenamiento_oci: AlmacenamientoOCISchema

    @model_validator(mode="after")
    def validar_items_segun_formato(self) -> "OutputExitoSchema":
        """Cruza el formato declarado con los items sin alterar el contrato JSON público."""
        indices_invalidos = indices_items_incompatibles(
            self.metadatos.formato_generado,
            self.contenido_adaptado.items,
        )
        if indices_invalidos:
            raise ValueError(
                f"Los items en las posiciones {indices_invalidos} no corresponden "
                f"al formato declarado {self.metadatos.formato_generado.value}."
            )
        return self


class OutputErrorSchema(ContractSchema):
    status: Literal["error"]
    error: ErrorSchema


OutputSchema = Annotated[
    Union[OutputExitoSchema, OutputErrorSchema],
    Field(discriminator="status"),
]

OUTPUT_SCHEMA_ADAPTER: TypeAdapter[OutputSchema] = TypeAdapter(OutputSchema)


def validar_output(payload: object) -> OutputSchema:
    """Valida una respuesta completa de éxito o error contra el contrato público."""
    return OUTPUT_SCHEMA_ADAPTER.validate_python(payload)
