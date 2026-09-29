"""
Implementación concreta de `LLMProvider` (ver llm_provider.py) sobre Google Gemini.

Es la única pieza de NM-08 que conoce detalles específicos de Gemini/LangChain-Google. El resto
de la orquestación (`orchestration_service`) depende solo del Protocol `LLMProvider`.
"""

from __future__ import annotations

from typing import TypeVar

import httpx
from google.genai.errors import APIError
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.core.config import settings
from app.services.llm_provider import LLMProviderError, LLMTimeoutError


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GeminiProvider:
    """Proveedor de LLM sobre Gemini, vía `langchain-google-genai`."""

    def __init__(
        self, *, model: str, api_key: str, timeout: float, reintentos: int = 3
    ) -> None:
        self._timeout = timeout
        self._intentos = reintentos + 1
        # `max_retries` del SDK cuenta intentos totales, incluido el pedido original.
        modelo_chat = ChatGoogleGenerativeAI(
            model=model, api_key=api_key, timeout=timeout, max_retries=self._intentos
        )
        self._modelo_chat = modelo_chat

    @classmethod
    def desde_configuracion(cls) -> "GeminiProvider":
        """Construye el proveedor leyendo la configuración de la aplicación (`app.core.config`)."""
        return cls(
            model=settings.GEMINI_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )

    def generate_structured(
        self,
        messages: list[BaseMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        try:
            modelo_estructurado = self._modelo_chat.with_structured_output(
                schema,
                method="json_schema",
            )
            resultado = modelo_estructurado.invoke(messages)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise LLMTimeoutError(
                f"Gemini no respondió tras {self._intentos} intento(s) de {self._timeout}s "
                "cada uno (GEMINI_TIMEOUT_SECONDS)."
            ) from exc
        except APIError as exc:
            raise LLMProviderError(f"Gemini devolvió un error de API: {exc}") from exc
        except Exception as exc:
            # Límite de la capa llm_provider: ningún fallo del SDK subyacente (de red, de
            # autenticación, etc.) debe cruzar sin traducirse a un error tipado propio.
            raise LLMProviderError(f"Fallo inesperado al invocar Gemini: {exc}") from exc

        if not isinstance(resultado, schema):
            raise LLMProviderError(
                "Gemini devolvió una respuesta que no coincide con el esquema solicitado."
            )
        return resultado
