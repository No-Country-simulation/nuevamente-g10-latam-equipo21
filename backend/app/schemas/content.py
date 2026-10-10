from pydantic import Field, StrictInt, StrictStr

from app.schemas.base import PublicSchema


class FlashcardItem(PublicSchema):
    frente: StrictStr = Field(
        ...,
        min_length=1,
        description="Contenido mostrado en el frente de la flashcard",
    )

    dorso: StrictStr = Field(
        ...,
        min_length=1,
        description="Contenido mostrado en el dorso de la flashcard",
    )

    pista_didactica: StrictStr = Field(
        ...,
        min_length=1,
        description="Pista didáctica para facilitar la comprensión",
    )


class QuizItem(PublicSchema):
    pregunta: StrictStr = Field(..., min_length=1)
    opciones: list[StrictStr] = Field(..., min_length=2)
    respuesta_correcta: StrictStr = Field(..., min_length=1)
    justificacion: StrictStr = Field(..., min_length=1)


class TutorialItem(PublicSchema):
    paso_numero: StrictInt = Field(..., ge=1)
    titulo_paso: StrictStr = Field(..., min_length=1)
    contenido: StrictStr = Field(..., min_length=1)
    codigo_ejemplo: StrictStr | None = None


class ResumenItem(PublicSchema):
    punto_clave: StrictStr = Field(..., min_length=1)
    descripcion: StrictStr = Field(..., min_length=1)
    impacto_negocio: StrictStr = Field(..., min_length=1)


class GuionItem(PublicSchema):
    seccion: StrictStr = Field(..., min_length=1)
    tiempo_estimado_minutos: StrictInt = Field(..., ge=1)
    narracion: StrictStr = Field(..., min_length=1)
    notas_visuales: StrictStr | None = None
