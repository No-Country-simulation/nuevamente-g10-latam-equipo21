"""
Implementación concreta de `LLMProvider` (ver llm_provider.py) sobre Google Gemini.

Es la única pieza de NM-08 que conoce detalles específicos de Gemini/LangChain-Google. El resto
de la orquestación (`orchestration_service`) depende solo del Protocol `LLMProvider`.
"""

from __future__ import annotations

from typing import Any

import httpx
from google.genai.errors import APIError
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.services.llm_provider import LLMProviderError, LLMTimeoutError


class GeminiProvider:
    """Proveedor de LLM sobre Gemini, vía `langchain-google-genai`."""

    def __init__(self, *, model: str, api_key: str, timeout: float) -> None:
        self._timeout = timeout
        modelo_chat = ChatGoogleGenerativeAI(model=model, api_key=api_key, timeout=timeout)
        # `response_mime_type` activa el modo JSON de Gemini sin atar la orquestación a un
        # schema concreto: la validación estricta contra el contrato (NM-07) queda para una
        # capa posterior que todavía no existe en el repo.
        self._modelo_json = modelo_chat.bind(response_mime_type="application/json")
        self._parser = JsonOutputParser()

    @classmethod
    def desde_configuracion(cls) -> "GeminiProvider":
        """Construye el proveedor leyendo la configuración de la aplicación (`app.core.config`)."""
        return cls(
            model=settings.GEMINI_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )

    def generate_json(self, messages: list[BaseMessage]) -> dict[str, Any]:
        cadena = self._modelo_json | self._parser
        try:
            return cadena.invoke(messages)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise LLMTimeoutError(
                f"Gemini no respondió dentro de los {self._timeout}s configurados "
                "(GEMINI_TIMEOUT_SECONDS)."
            ) from exc
        except OutputParserException as exc:
            raise LLMProviderError(
                f"La respuesta de Gemini no pudo interpretarse como JSON: {exc}"
            ) from exc
        except APIError as exc:
            raise LLMProviderError(f"Gemini devolvió un error de API: {exc}") from exc
        except Exception as exc:
            # Límite de la capa llm_provider: ningún fallo del SDK subyacente (de red, de
            # autenticación, etc.) debe cruzar sin traducirse a un error tipado propio.
            raise LLMProviderError(f"Fallo inesperado al invocar Gemini: {exc}") from exc
