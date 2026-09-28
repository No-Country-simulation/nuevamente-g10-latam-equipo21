from typing import Literal

from pydantic import BaseModel, Field

class FlashcardItem(BaseModel):
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


class QuizItem(BaseModel):
    pregunta: str = Field(..., min_length=1)
    opciones: list[str] = Field(..., min_length=2)
    respuesta_correcta: str = Field(..., min_length=1)
    justificacion: str = Field(..., min_length=1)


class TutorialItem(BaseModel):
    paso_numero: int = Field(..., ge=1)
    titulo_paso: str = Field(..., min_length=1)
    contenido: str = Field(..., min_length=1)
    codigo_ejemplo: str | None = None


class ResumenItem(BaseModel):
    punto_clave: str = Field(..., min_length=1)
    descripcion: str = Field(..., min_length=1)
    impacto_negocio: str = Field(..., min_length=1)


class GuionItem(BaseModel):
    seccion: str = Field(..., min_length=1)
    tiempo_estimado_minutos: int = Field(..., ge=1)
    narracion: str = Field(..., min_length=1)
    notas_visuales: str | None = None




class FlashcardsContent(BaseModel):
    formato_salida: Literal["Flashcards"] = "Flashcards"
    items: list[FlashcardItem] = Field(
        ...,
        min_length=1,
        description="Lista de flashcards generadas",
    )


class QuizContent(BaseModel):
    formato_salida: Literal["Quiz"] = "Quiz"
    items: list[QuizItem] = Field(
        ...,
        min_length=1,
        description="Lista de preguntas del quiz",
    )


class TutorialContent(BaseModel):
    formato_salida: Literal["Tutorial"] = "Tutorial"
    items: list[TutorialItem] = Field(
        ...,
        min_length=1,
        description="Pasos o secciones del tutorial",
    )


class ResumenContent(BaseModel):
    formato_salida: Literal["Resumen Ejecutivo"] = "Resumen Ejecutivo"
    items: list[ResumenItem] = Field(
        ...,
        min_length=1,
        description="Secciones del resumen ejecutivo",
    )


class GuionContent(BaseModel):
    formato_salida: Literal["Guion"] = "Guion"
    items: list[GuionItem] = Field(
        ...,
        min_length=1,
        description="Secciones del guion generado",
    )
