"""
Tests de GeminiProvider con el cliente de Gemini reemplazado por un doble de prueba: nunca se
abre una conexión real ni se requiere una GEMINI_API_KEY válida.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from app.services import gemini_provider as gemini_provider_module
from app.services.gemini_provider import GeminiProvider
from app.services.llm_provider import LLMProviderError, LLMTimeoutError


class _ChatModelFalso:
    """
    Reemplaza a ChatGoogleGenerativeAI: expone la misma superficie mínima que usa GeminiProvider
    (bind + invoke) y soporta el operador `|` para componerse con el JsonOutputParser real.
    """

    def __init__(self, *, contenido: str | None = None, excepcion: BaseException | None = None):
        self._contenido = contenido
        self._excepcion = excepcion

    def bind(self, **_kwargs) -> "_ChatModelFalso":
        return self

    def invoke(self, _messages, *_args, **_kwargs):
        if self._excepcion is not None:
            raise self._excepcion
        return AIMessage(content=self._contenido)

    def __or__(self, siguiente_paso):
        return RunnableLambda(lambda entrada: siguiente_paso.invoke(self.invoke(entrada)))


def _crear_provider(monkeypatch: pytest.MonkeyPatch, chat_model_falso: _ChatModelFalso) -> GeminiProvider:
    monkeypatch.setattr(
        gemini_provider_module,
        "ChatGoogleGenerativeAI",
        lambda **_kwargs: chat_model_falso,
    )
    return GeminiProvider(model="gemini-3.8-flash", api_key="fake-key-no-real", timeout=1.0)


def test_generate_json_devuelve_el_json_parseado(monkeypatch):
    falso = _ChatModelFalso(contenido='{"titulo": "Índices", "items": []}')
    provider = _crear_provider(monkeypatch, falso)

    resultado = provider.generate_json([HumanMessage(content="hola")])

    assert resultado == {"titulo": "Índices", "items": []}


def test_generate_json_traduce_timeout_a_llm_timeout_error(monkeypatch):
    falso = _ChatModelFalso(excepcion=TimeoutError("se venció el tiempo de espera"))
    provider = _crear_provider(monkeypatch, falso)

    with pytest.raises(LLMTimeoutError):
        provider.generate_json([HumanMessage(content="hola")])


def test_generate_json_traduce_fallo_generico_a_llm_provider_error(monkeypatch):
    falso = _ChatModelFalso(excepcion=RuntimeError("fallo inesperado del SDK"))
    provider = _crear_provider(monkeypatch, falso)

    with pytest.raises(LLMProviderError):
        provider.generate_json([HumanMessage(content="hola")])


def test_generate_json_traduce_json_invalido_a_llm_provider_error(monkeypatch):
    falso = _ChatModelFalso(contenido="esto no es JSON")
    provider = _crear_provider(monkeypatch, falso)

    with pytest.raises(LLMProviderError):
        provider.generate_json([HumanMessage(content="hola")])


def test_no_depende_de_una_gemini_api_key_real(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    falso = _ChatModelFalso(contenido="{}")
    provider = _crear_provider(monkeypatch, falso)

    assert provider.generate_json([HumanMessage(content="hola")]) == {}
