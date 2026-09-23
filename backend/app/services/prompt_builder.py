"""
Construcción de los mensajes de prompt para la orquestación de adaptación de contenido (NM-08).

Combina el prompt base versionado (prompts/adaptacion_base.md, contenido estático) con las
instrucciones de personalización por eje (prompts/personalizacion.py) y los datos propios de la
petición, usando las utilidades de LangChain (`PromptTemplate`, tipos de mensaje) definidas como
framework de orquestación en NM-01.

El prompt base se mantiene fuera de `ChatPromptTemplate` a propósito: es texto estático que
incluye ejemplos JSON con llaves literales, y `ChatPromptTemplate` interpretaría esas llaves
como variables de template si se lo cargara como un mensaje templado.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

from app.services.prompts import personalizacion

_PROMPT_BASE_PATH = Path(__file__).parent / "prompts" / "adaptacion_base.md"

_HUMAN_TEMPLATE = PromptTemplate.from_template(
    'Documento fuente: "{documento_titulo}"\n\n'
    "Contexto recuperado (única fuente de verdad permitida para el contenido factual):\n"
    "{contexto_recuperado}\n\n"
    "Instrucciones de personalización para esta adaptación:\n"
    "- Perfil del destinatario: {instrucciones_perfil}\n"
    "- Formato de salida solicitado: {instrucciones_formato}\n"
    "  Ejemplo de un item en ese formato: {ejemplo_item_formato}\n"
    "- Nicho / sector: {instrucciones_nicho}\n"
    "- Nivel de detalle: {instrucciones_nivel_detalle}\n\n"
    'Generá el JSON de "contenido_adaptado" siguiendo estrictamente las reglas indicadas en el '
    "mensaje de sistema."
)


@lru_cache(maxsize=1)
def _cargar_prompt_base() -> str:
    return _PROMPT_BASE_PATH.read_text(encoding="utf-8")


def construir_mensajes_adaptacion(
    *,
    documento_titulo: str,
    contexto_recuperado: str,
    perfil_destinatario: str,
    formato_salida: str,
    nicho_sector: str,
    nivel_detalle: str,
) -> list[BaseMessage]:
    """
    Arma los mensajes (sistema + humano) para la cadena de adaptación de contenido.

    `contexto_recuperado` se trata como texto opaco ya ensamblado (responsabilidad de NM-06,
    pendiente de integración): este builder no asume ninguna estructura interna sobre cómo se
    obtuvo ese contexto, solo lo incorpora al prompt.

    Los cuatro parámetros de personalización se esperan como los strings literales del contrato
    documentado en docs/ARCHITECTURE.md. Un valor fuera de esos literales hace fallar esta
    función con un `KeyError` explícito (la validación formal de esos valores es responsabilidad
    de los esquemas de NM-07, todavía no integrados).
    """
    formato_info = personalizacion.INSTRUCCIONES_FORMATO[formato_salida]

    mensaje_humano = _HUMAN_TEMPLATE.format(
        documento_titulo=documento_titulo,
        contexto_recuperado=contexto_recuperado,
        instrucciones_perfil=personalizacion.INSTRUCCIONES_PERFIL[perfil_destinatario],
        instrucciones_formato=formato_info["instrucciones"],
        ejemplo_item_formato=formato_info["ejemplo_item"],
        instrucciones_nicho=personalizacion.INSTRUCCIONES_NICHO[nicho_sector],
        instrucciones_nivel_detalle=personalizacion.INSTRUCCIONES_NIVEL_DETALLE[nivel_detalle],
    )

    return [
        SystemMessage(content=_cargar_prompt_base()),
        HumanMessage(content=mensaje_humano),
    ]
