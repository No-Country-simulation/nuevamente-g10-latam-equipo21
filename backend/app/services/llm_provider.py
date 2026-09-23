"""
Capa de desacople entre la orquestación de NM-08 y cualquier proveedor concreto de LLM.

`orchestration_service` depende exclusivamente del Protocol `LLMProvider` definido acá, nunca
de un SDK específico. Esto permite reemplazar Gemini por otro proveedor implementando este
mismo contrato, sin modificar el resto del pipeline (criterio de aceptación de NM-08).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from langchain_core.messages import BaseMessage


class LLMProviderError(Exception):
    """Fallo genérico al invocar el proveedor de LLM."""


class LLMTimeoutError(LLMProviderError):
    """El proveedor de LLM no respondió dentro del timeout configurado."""


@runtime_checkable
class LLMProvider(Protocol):
    """Contrato mínimo que debe cumplir cualquier proveedor de LLM usado por NM-08."""

    def generate_json(self, messages: list[BaseMessage]) -> dict[str, Any]:
        """
        Envía `messages` al modelo y devuelve la respuesta ya parseada como JSON.

        Implementaciones concretas deben levantar `LLMTimeoutError` ante un timeout y
        `LLMProviderError` ante cualquier otro fallo del proveedor (error de API, respuesta no
        parseable como JSON, etc.): nunca deben dejar la excepción específica del SDK subyacente
        propagarse sin traducir, ni dejar la llamada colgada.
        """
        ...
