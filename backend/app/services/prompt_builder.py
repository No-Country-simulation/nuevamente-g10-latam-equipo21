"""
Construcción de los mensajes de prompt para la orquestación de adaptación de contenido (NM-08).

Combina el prompt base versionado (prompts/adaptacion_base.md, contenido estático), la plantilla
del mensaje de usuario (prompts/adaptacion_usuario.md) y las instrucciones de personalización por
eje (prompts/personalizacion.py) con los datos propios de la petición, usando las utilidades de
LangChain (`PromptTemplate`, tipos de mensaje) definidas como framework de orquestación en NM-01.

El prompt base se mantiene fuera de `ChatPromptTemplate` a propósito: es texto estático que
incluye ejemplos JSON con llaves literales, y `ChatPromptTemplate` interpretaría esas llaves
como variables de template si se lo cargara como un mensaje templado.
"""

"""
Construcción de los mensajes de prompt para la orquestación
de adaptación de contenido (NM-08).

NM-D1 extiende este builder permitiendo agregar feedback del
Agente Crítico cuando el contenido necesita una nueva iteración,
sin modificar el comportamiento original cuando no existe feedback.
"""

from functools import lru_cache
from pathlib import Path

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.prompts import PromptTemplate

from app.services.prompts import personalizacion


_PROMPT_BASE_PATH = (
    Path(__file__).parent
    / "prompts"
    / "adaptacion_base.md"
)

_PROMPT_USUARIO_PATH = (
    Path(__file__).parent
    / "prompts"
    / "adaptacion_usuario.md"
)

_PROMPT_REVISION_PATH = (
    Path(__file__).parent
    / "prompts"
    / "revision_critica.md"
)


@lru_cache(maxsize=1)
def _cargar_prompt_base() -> str:
    return _PROMPT_BASE_PATH.read_text(
        encoding="utf-8"
    )


@lru_cache(maxsize=1)
def _cargar_plantilla_usuario() -> PromptTemplate:
    return PromptTemplate.from_template(
        _PROMPT_USUARIO_PATH.read_text(
            encoding="utf-8"
        ).rstrip("\n")
    )


@lru_cache(maxsize=1)
def _cargar_plantilla_revision() -> PromptTemplate:
    return PromptTemplate.from_template(
        _PROMPT_REVISION_PATH.read_text(
            encoding="utf-8"
        ).rstrip("\n")
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
) -> list[BaseMessage]:
    """
    Construye los mensajes para generar contenido adaptado.

    Cuando feedback_critico no está presente, mantiene
    el comportamiento original de NM-08.

    Cuando existe feedback, agrega un mensaje adicional
    con las observaciones del Agente Crítico para orientar
    la reescritura.
    """

    formato_info = (
        personalizacion.INSTRUCCIONES_FORMATO[
            formato_salida
        ]
    )

    mensaje_humano = (
        _cargar_plantilla_usuario().format(
            documento_titulo=documento_titulo,
            contexto_recuperado=contexto_recuperado,
            instrucciones_perfil=(
                personalizacion.INSTRUCCIONES_PERFIL[
                    perfil_destinatario
                ]
            ),
            instrucciones_formato=(
                formato_info["instrucciones"]
            ),
            ejemplo_item_formato=(
                formato_info["ejemplo_item"]
            ),
            instrucciones_nicho=(
                personalizacion.INSTRUCCIONES_NICHO[
                    nicho_sector
                ]
            ),
            instrucciones_nivel_detalle=(
                personalizacion
                .INSTRUCCIONES_NIVEL_DETALLE[
                    nivel_detalle
                ]
            ),
        )
    )

    mensajes: list[BaseMessage] = [
        SystemMessage(
            content=_cargar_prompt_base()
        ),
        HumanMessage(
            content=mensaje_humano
        ),
    ]

    if (
        feedback_critico is not None
        and feedback_critico.strip()
    ):
        mensaje_revision = (
            _cargar_plantilla_revision().format(
                feedback_critico=(
                    feedback_critico.strip()
                )
            )
        )

        mensajes.append(
            HumanMessage(
                content=mensaje_revision
            )
        )

    return mensajes