"""
Orquestación de la generación de contenido adaptado (NM-08).

Combina el contexto recuperado por NM-06 y los parámetros de
personalización en un prompt, y lo ejecuta contra un `LLMProvider` (ver llm_provider.py) para
obtener contenido adaptado validado contra el esquema de NM-07.

Este módulo no importa nada de Gemini ni de ningún proveedor concreto: recibe `llm_provider`
por parámetro, lo que permite reemplazar el proveedor sin modificar esta función.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.content import (
    FlashcardItem,
    GuionItem,
    QuizItem,
    ResumenItem,
    TutorialItem,
)
from app.schemas.enums import FormatoSalida
from app.schemas.output import ContenidoAdaptadoSchema
from app.services.llm_provider import LLMProvider
from app.services.prompt_builder import construir_mensajes_adaptacion


class ContenidoAdaptadoInvalidoError(ValueError):
    """El contenido validó estructuralmente, pero no corresponde al formato solicitado."""


TIPO_ITEM_POR_FORMATO: dict[FormatoSalida, type[BaseModel]] = {
    FormatoSalida.TUTORIAL: TutorialItem,
    FormatoSalida.FLASHCARDS: FlashcardItem,
    FormatoSalida.QUIZ: QuizItem,
    FormatoSalida.RESUMEN_EJECUTIVO: ResumenItem,
    FormatoSalida.GUION_CLASE: GuionItem,
}


def _indices_items_incompatibles(
    formato_salida: FormatoSalida | str,
    items: list[BaseModel],
) -> list[int]:
    """Devuelve las posiciones cuyos items no corresponden al formato solicitado."""
    formato = FormatoSalida(formato_salida)
    tipo_esperado = TIPO_ITEM_POR_FORMATO[formato]
    return [
        indice
        for indice, item in enumerate(items)
        if not isinstance(item, tipo_esperado)
    ]


def generar_contenido_adaptado(
    *,
    documento_titulo: str,
    contexto_recuperado: str,
    perfil_destinatario: str,
    formato_salida: str,
    nicho_sector: str,
    nivel_detalle: str,
    llm_provider: LLMProvider,
    feedback_critico: str | None = None,
) -> ContenidoAdaptadoSchema:
    """
    Genera el contenido adaptado para un documento, anclado al contexto recuperado.

    `contexto_recuperado` es texto ya ensamblado por el proceso de recuperación semántica
    (NM-06); esta función lo trata como dato opaco, sin asumir cómo se obtuvo.

    Devuelve `ContenidoAdaptadoSchema`, validado por el proveedor mediante structured output.
    Además comprueba que cada item corresponda al `formato_salida` solicitado, ya que la unión
    de items de NM-07 no tiene un discriminador que permita cruzar ambos datos automáticamente.

    Levanta `LLMTimeoutError`/`LLMProviderError` (ver llm_provider.py) si el proveedor falla o
    no responde a tiempo; nunca deja la llamada colgada.
    """
    mensajes = construir_mensajes_adaptacion(
        documento_titulo=documento_titulo,
        contexto_recuperado=contexto_recuperado,
        perfil_destinatario=perfil_destinatario,
        formato_salida=formato_salida,
        nicho_sector=nicho_sector,
        nivel_detalle=nivel_detalle,
        feedback_critico=feedback_critico,
    )
    resultado = llm_provider.generate_structured(mensajes, ContenidoAdaptadoSchema)

    indices_invalidos = _indices_items_incompatibles(formato_salida, resultado.items)
    if indices_invalidos:
        raise ContenidoAdaptadoInvalidoError(
            f"Los items en las posiciones {indices_invalidos} no corresponden "
            f"al formato solicitado {formato_salida}."
        )

    return resultado
