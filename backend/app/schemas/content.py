from typing import Literal

from pydantic import BaseModel, Field


class FlashcardItem(BaseModel):
    pregunta: str = Field(
        ...,
        min_length=3,
        description="Pregunta o concepto presentado en la flashcard",
    )

    respuesta: str = Field(
        ...,
        min_length=3,
        description="Respuesta o explicación asociada a la flashcard",
    )


class QuizItem(BaseModel):
    pregunta: str = Field(
        ...,
        min_length=3,
        description="Pregunta del quiz",
    )

    opciones: list[str] = Field(
        ...,
        min_length=2,
        description="Opciones disponibles para responder la pregunta",
    )

    respuesta_correcta: str = Field(
        ...,
        min_length=1,
        description="Respuesta correcta de la pregunta",
    )

    justificacion: str = Field(
        ...,
        min_length=3,
        description="Explicación de por qué la respuesta indicada es correcta",
    )


class TutorialItem(BaseModel):
    titulo: str = Field(
        ...,
        min_length=3,
        description="Título del paso o sección del tutorial",
    )

    explicacion: str = Field(
        ...,
        min_length=10,
        description="Explicación detallada del paso o sección",
    )

    ejemplo: str | None = Field(
        default=None,
        description="Ejemplo opcional relacionado con el paso del tutorial",
    )


class ResumenItem(BaseModel):
    titulo: str = Field(
        ...,
        min_length=3,
        description="Título de la sección del resumen ejecutivo",
    )

    contenido: str = Field(
        ...,
        min_length=10,
        description="Contenido resumido de la sección",
    )

    puntos_clave: list[str] = Field(
        ...,
        min_length=1,
        description="Principales puntos clave identificados en la sección",
    )


class GuionItem(BaseModel):
    seccion: str = Field(
        ...,
        min_length=3,
        description="Nombre de la sección del guion",
    )

    narracion: str = Field(
        ...,
        min_length=10,
        description="Texto que será narrado o presentado en la sección",
    )

    indicaciones: str | None = Field(
        default=None,
        description="Indicaciones opcionales de apoyo para la presentación o producción",
    )




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
