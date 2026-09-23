"""
Orquestación de la generación de contenido adaptado (NM-08).

Combina el contexto recuperado (NM-06, pendiente de integración) y los parámetros de
personalización en un prompt, y lo ejecuta contra un `LLMProvider` (ver llm_provider.py) para
obtener el JSON generado por el modelo.

Este módulo no importa nada de Gemini ni de ningún proveedor concreto: recibe `llm_provider`
por parámetro, lo que permite reemplazar el proveedor sin modificar esta función.
"""

from __future__ import annotations

from typing import Any

from app.services.llm_provider import LLMProvider
from app.services.prompt_builder import construir_mensajes_adaptacion


def generar_contenido_adaptado(
    *,
    documento_titulo: str,
    contexto_recuperado: str,
    perfil_destinatario: str,
    formato_salida: str,
    nicho_sector: str,
    nivel_detalle: str,
    llm_provider: LLMProvider,
) -> dict[str, Any]:
    """
    Genera el contenido adaptado para un documento, anclado al contexto recuperado.

    `contexto_recuperado` es texto ya ensamblado por el proceso de recuperación semántica
    (NM-06, pendiente de integración); esta función lo trata como dato opaco, sin asumir cómo
    se obtuvo.

    Devuelve el `dict` con el JSON crudo generado por el LLM, sin validar contra el contrato
    estricto de `contenido_adaptado` (NM-07, pendiente de integración): quien invoque esta
    función es responsable de aplicar esa validación antes de usar el resultado como respuesta
    de la API.

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
    )
    return llm_provider.generate_json(mensajes)
