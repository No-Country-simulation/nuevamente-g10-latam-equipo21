"""
Construcción de los mensajes de prompt para la orquestación de adaptación de contenido (NM-08).

Combina el prompt base versionado (prompts/adaptacion_base.md, contenido estático), la plantilla
del mensaje de usuario (prompts/adaptacion_usuario.md) y las instrucciones de personalización por
eje (prompts/personalizacion.py) con los datos propios de la petición, usando las utilidades de
LangChain (`PromptTemplate`, tipos de mensaje) definidas como framework de orquestación en NM-01.

El prompt base se mantiene fuera de `ChatPromptTemplate` a propósito: es texto estático que
incluye ejemplos JSON con llaves literales, y `ChatPromptTemplate` interpretaría esas llaves
como variables de template si se lo cargara como un mensaje templado.

Construcción de los mensajes de prompt para la adaptación de contenido.

Combina el prompt base de NM-08, las instrucciones de personalización
y, cuando NM-D1 solicita una reescritura, incorpora la versión anterior
del contenido junto con las observaciones del Agente Crítico.
"""

from __future__ import annotations

from functools import lru_cache
import math
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

from app.services.prompts import personalizacion


_PROMPT_BASE_PATH = Path(__file__).parent / "prompts" / "adaptacion_base.md"
_PROMPT_USUARIO_PATH = Path(__file__).parent / "prompts" / "adaptacion_usuario.md"
_PROMPT_REVISION_PATH = Path(__file__).parent / "prompts" / "revision_critica.md"


@lru_cache(maxsize=1)
def _cargar_prompt_base() -> str:
    return _PROMPT_BASE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _cargar_plantilla_usuario() -> PromptTemplate:
    return PromptTemplate.from_template(
        _PROMPT_USUARIO_PATH.read_text(encoding="utf-8").rstrip("\n")
    )


@lru_cache(maxsize=1)
def _cargar_plantilla_revision() -> PromptTemplate:
    return PromptTemplate.from_template(
        _PROMPT_REVISION_PATH.read_text(encoding="utf-8").rstrip("\n")
    )


# NM-33: rango de items por formato (minimo, maximo). El ticket solo da el ejemplo del Quiz
# (5 a 10); el resto es decision de diseño y se ajusta aqui.
_RANGO_ITEMS = {
    "Quiz": (5, 10),
    "Tutorial": (5, 10),
    "Flashcards": (6, 12),
    "Resumen_Ejecutivo": (6, 12),
    "Guion_Clase": (4, 8),
}
_CARACTERES_POR_ITEM = 500  # estimacion: un item cada ~500 caracteres de contexto


def _instruccion_cantidad(formato_salida: str, contexto_recuperado: str) -> str:
    minimo, maximo = _RANGO_ITEMS.get(formato_salida, (4, 8))
    sugerido = math.ceil(len(contexto_recuperado) / _CARACTERES_POR_ITEM)
    objetivo = min(maximo, max(minimo, sugerido))
    return (
        f"genera entre {objetivo} y {maximo} items y cubre todos los temas del contexto "
        "recuperado, con al menos un item por tema. Si hay mas temas que el maximo, agrupa "
        "los relacionados. Si el contexto no alcanza para ese minimo, genera menos items "
        "en lugar de inventar informacion."
    )


def construir_mensajes_adaptacion(
    *,
    documento_titulo: str,
    contexto_recuperado: str,
    perfil_destinatario: str,
    formato_salida: str,
    nicho_sector: str,
    nivel_detalle: str,
    feedback_critico: str | None = None,
    contenido_anterior_serializado: str | None = None,
) -> list[BaseMessage]:
    """
    Arma los mensajes para generar o revisar contenido adaptado.

    Sin feedback mantiene el comportamiento de NM-08.
    Cuando existe feedback del Crítico, exige también la versión anterior
    serializada para que el Redactor pueda corregir el contenido que fue evaluado.
    """
    formato_info = personalizacion.INSTRUCCIONES_FORMATO[formato_salida]

    mensaje_humano = _cargar_plantilla_usuario().format(
        documento_titulo=documento_titulo,
        contexto_recuperado=contexto_recuperado,
        instruccion_cantidad=_instruccion_cantidad(formato_salida, contexto_recuperado),
        instrucciones_perfil=personalizacion.INSTRUCCIONES_PERFIL[
            perfil_destinatario
        ],
        instrucciones_formato=formato_info["instrucciones"],
        ejemplo_item_formato=formato_info["ejemplo_item"],
        instrucciones_nicho=personalizacion.INSTRUCCIONES_NICHO[nicho_sector],
        instrucciones_nivel_detalle=(
            personalizacion.INSTRUCCIONES_NIVEL_DETALLE[nivel_detalle]
        ),
    )

    mensajes: list[BaseMessage] = [
        SystemMessage(content=_cargar_prompt_base()),
        HumanMessage(content=mensaje_humano),
    ]

    if feedback_critico is not None and feedback_critico.strip():
        if (
            contenido_anterior_serializado is None
            or not contenido_anterior_serializado.strip()
        ):
            raise ValueError(
                "El feedback del Crítico requiere el contenido anterior."
            )

        mensaje_revision = _cargar_plantilla_revision().format(
            contenido_anterior=contenido_anterior_serializado.strip(),
            feedback_critico=feedback_critico.strip(),
        )

        mensajes.append(HumanMessage(content=mensaje_revision))

    return mensajes