from pydantic import Field

from app.schemas.base import ContractSchema


class FlashcardItem(ContractSchema):
    frente: str = Field(
        ...,
        min_length=1,
        description="Contenido mostrado en el frente de la flashcard",
    )

    dorso: str = Field(
        ...,
        min_length=1,
        description="Contenido mostrado en el dorso de la flashcard",
    )

    pista_didactica: str = Field(
        ...,
        min_length=1,
        description="Pista didáctica para facilitar la comprensión",
    )


class QuizItem(ContractSchema):
    pregunta: str = Field(..., min_length=1)
    opciones: list[str] = Field(..., min_length=4, max_length=4)
    respuesta_correcta: str = Field(..., min_length=1)
    justificacion: str = Field(..., min_length=1)


class TutorialItem(ContractSchema):
    paso_numero: int = Field(..., ge=1)
    titulo_paso: str = Field(..., min_length=1)
    contenido: str = Field(..., min_length=1)
    codigo_ejemplo: str | None


class ResumenItem(ContractSchema):
    punto_clave: str = Field(..., min_length=1)
    descripcion: str = Field(..., min_length=1)
    impacto_negocio: str = Field(..., min_length=1)


class GuionItem(ContractSchema):
    seccion: str = Field(..., min_length=1)
    tiempo_estimado_minutos: int = Field(..., ge=1)
    narracion: str = Field(..., min_length=1)
    notas_visuales: str = Field(..., min_length=1)
