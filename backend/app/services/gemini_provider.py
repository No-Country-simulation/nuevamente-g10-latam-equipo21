"""
Implementación concreta de `LLMProvider` (ver llm_provider.py) sobre Google Gemini.

Es la única pieza de NM-08 que conoce detalles específicos de Gemini/LangChain-Google. El resto
de la orquestación (`orchestration_service`) depende solo del Protocol `LLMProvider`.
"""

from __future__ import annotations

import logging
from typing import TypeVar

import httpx
from google.genai.errors import APIError
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.core.config import settings
from app.services.llm_provider import LLMProviderError, LLMTimeoutError


SchemaT = TypeVar("SchemaT", bound=BaseModel)
logger = logging.getLogger(__name__)


class GeminiProvider:
    """Proveedor de LLM sobre Gemini, vía `langchain-google-genai`."""

    def __init__(
        self, *, model: str, api_key: str, timeout: float, reintentos: int = 3,
        fallback_model: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._intentos = reintentos + 1
        fallback_model = (fallback_model or "").strip()
        if fallback_model == model:
            raise ValueError("El modelo de respaldo debe ser distinto del principal.")
        # `max_retries` del SDK cuenta intentos totales, incluido el pedido original.
        self._modelo_chat = ChatGoogleGenerativeAI(
            model=model, api_key=api_key, timeout=timeout, max_retries=self._intentos
        )
        self._modelo_respaldo = (
            ChatGoogleGenerativeAI(
                model=fallback_model, api_key=api_key, timeout=timeout,
                max_retries=self._intentos,
            )
            if fallback_model else None
        )
        self._nombre_modelo = model
        self._nombre_respaldo = fallback_model

    @classmethod
    def desde_configuracion(cls) -> "GeminiProvider":
        """Construye el proveedor leyendo la configuración de la aplicación (`app.core.config`)."""
        return cls(
            model=settings.GEMINI_MODEL_NAME,
            fallback_model=settings.GEMINI_FALLBACK_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )

    def generate_structured(
        self,
        messages: list[BaseMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        try:
            try:
                resultado = self._invocar(self._modelo_chat, messages, schema)
            except APIError as exc:
                if self._modelo_respaldo is None or not self._permite_respaldo(exc):
                    raise
                logger.warning(
                    "Gemini usa modelo de respaldo principal=%s respaldo=%s motivo=%s",
                    self._nombre_modelo, self._nombre_respaldo, f"{exc.code}/{exc.status}",
                )
                resultado = self._invocar(self._modelo_respaldo, messages, schema)
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

    @staticmethod
    def _permite_respaldo(exc: APIError) -> bool:
        return exc.code in (429, 503) or exc.status in (
            "RESOURCE_EXHAUSTED", "UNAVAILABLE"
        )

    @staticmethod
    def _invocar(
        modelo_chat: ChatGoogleGenerativeAI,
        messages: list[BaseMessage],
        schema: type[SchemaT],
    ) -> SchemaT:
        return modelo_chat.with_structured_output(
            schema, method="json_schema"
        ).invoke(messages)
