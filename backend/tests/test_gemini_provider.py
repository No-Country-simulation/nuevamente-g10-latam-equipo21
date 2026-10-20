"""
Tests de GeminiProvider con el cliente de Gemini reemplazado por un doble de prueba: nunca se
abre una conexión real ni se requiere una GEMINI_API_KEY válida.
"""

from __future__ import annotations

import json

import pytest
from google.genai.errors import APIError
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from app.services import gemini_provider as gemini_provider_module
from app.services.gemini_provider import GeminiProvider
from app.services.llm_provider import LLMProviderError, LLMTimeoutError


class _ChatModelFalso:
    """
    Reemplaza a ChatGoogleGenerativeAI: expone la misma superficie mínima que usa GeminiProvider
    (`with_structured_output`) sin abrir una conexión real.
    """

    def __init__(self, *, contenido: str | None = None, excepcion: BaseException | None = None):
        self._contenido = contenido
        self._excepcion = excepcion
        self.invocaciones = 0
        self.mensajes_recibidos = None

        self.schema_recibido: type[BaseModel] | None = None
        self.metodo_recibido: str | None = None

    def with_structured_output(
        self,
        schema: type[BaseModel],
        *,
        method: str,
    ) -> RunnableLambda:
        self.schema_recibido = schema
        self.metodo_recibido = method

        def _invocar(messages):
            self.invocaciones += 1
            self.mensajes_recibidos = messages
            if self._excepcion is not None:
                raise self._excepcion
            assert self._contenido is not None
            return schema.model_validate(json.loads(self._contenido))

        return RunnableLambda(_invocar)


class _RespuestaPrueba(BaseModel):
    titulo: str
    items: list[dict]


def _crear_provider(monkeypatch: pytest.MonkeyPatch, chat_model_falso: _ChatModelFalso) -> GeminiProvider:
    monkeypatch.setattr(
        gemini_provider_module,
        "ChatGoogleGenerativeAI",
        lambda **_kwargs: chat_model_falso,
    )
    return GeminiProvider(model="gemini-3.8-flash", api_key="fake-key-no-real", timeout=1.0)


def _crear_provider_con_respaldo(
    monkeypatch: pytest.MonkeyPatch,
    principal: _ChatModelFalso,
    respaldo: _ChatModelFalso,
) -> GeminiProvider:
    modelos = {"modelo-principal": principal, "modelo-respaldo": respaldo}
    monkeypatch.setattr(
        gemini_provider_module,
        "ChatGoogleGenerativeAI",
        lambda **kwargs: modelos[kwargs["model"]],
    )
    return GeminiProvider(
        model="modelo-principal", fallback_model="modelo-respaldo",
        api_key="fake-key-no-real", timeout=1.0,
    )


def _error_api(code: int, status: str) -> APIError:
    return APIError(code, {"error": {"status": status, "message": "fallo simulado"}})


def test_generate_structured_devuelve_el_modelo_validado(monkeypatch):
    falso = _ChatModelFalso(contenido='{"titulo": "Índices", "items": []}')
    provider = _crear_provider(monkeypatch, falso)

    resultado = provider.generate_structured(
        [HumanMessage(content="hola")],
        _RespuestaPrueba,
    )

    assert resultado == _RespuestaPrueba(titulo="Índices", items=[])
    assert falso.schema_recibido is _RespuestaPrueba
    assert falso.metodo_recibido == "json_schema"


def test_generate_json_traduce_timeout_a_llm_timeout_error(monkeypatch):
    falso = _ChatModelFalso(excepcion=TimeoutError("se venció el tiempo de espera"))
    provider = _crear_provider(monkeypatch, falso)

    with pytest.raises(LLMTimeoutError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)


def test_generate_json_traduce_fallo_generico_a_llm_provider_error(monkeypatch):
    falso = _ChatModelFalso(excepcion=RuntimeError("fallo inesperado del SDK"))
    provider = _crear_provider(monkeypatch, falso)

    with pytest.raises(LLMProviderError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)


def test_generate_json_traduce_json_invalido_a_llm_provider_error(monkeypatch):
    falso = _ChatModelFalso(contenido="esto no es JSON")
    provider = _crear_provider(monkeypatch, falso)

    with pytest.raises(LLMProviderError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)


def test_reintentos_se_traducen_a_intentos_totales_del_sdk(monkeypatch):
    """
    El SDK cuenta intentos totales en `max_retries` (incluye el pedido original): 3 reintentos
    equivalen a 4 intentos, y 0 reintentos a un único intento. Un default implícito del SDK
    (6 intentos) dejaría la petición esperando mucho más que GEMINI_TIMEOUT_SECONDS.
    """
    capturado: dict = {}

    def _fabrica(**kwargs):
        capturado.update(kwargs)
        return _ChatModelFalso(contenido="{}")

    monkeypatch.setattr(gemini_provider_module, "ChatGoogleGenerativeAI", _fabrica)

    GeminiProvider(model="modelo-de-prueba", api_key="fake-key-no-real", timeout=1.0)
    assert capturado["max_retries"] == 4

    GeminiProvider(model="modelo-de-prueba", api_key="fake-key-no-real", timeout=1.0, reintentos=0)
    assert capturado["max_retries"] == 1


def test_no_depende_de_una_gemini_api_key_real(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    falso = _ChatModelFalso(contenido="{}")
    provider = _crear_provider(monkeypatch, falso)

    class _RespuestaVacia(BaseModel):
        pass

    assert provider.generate_structured(
        [HumanMessage(content="hola")], _RespuestaVacia
    ) == _RespuestaVacia()


@pytest.mark.parametrize(
    ("code", "status"),
    [(429, "RESOURCE_EXHAUSTED"), (503, "UNAVAILABLE")],
)
def test_usa_respaldo_solo_ante_cuota_o_indisponibilidad(
    monkeypatch, caplog, code, status,
):
    principal = _ChatModelFalso(excepcion=_error_api(code, status))
    respaldo = _ChatModelFalso(contenido='{"titulo": "Índices", "items": []}')
    provider = _crear_provider_con_respaldo(monkeypatch, principal, respaldo)
    mensajes = [HumanMessage(content="pedido de prueba")]

    resultado = provider.generate_structured(mensajes, _RespuestaPrueba)

    assert resultado == _RespuestaPrueba(titulo="Índices", items=[])
    assert principal.invocaciones == respaldo.invocaciones == 1
    assert principal.mensajes_recibidos == respaldo.mensajes_recibidos == mensajes
    assert respaldo.schema_recibido is _RespuestaPrueba
    assert f"motivo={code}/{status}" in caplog.text
    assert "modelo-respaldo" in caplog.text
    assert "pedido de prueba" not in caplog.text


def test_no_usa_respaldo_si_el_principal_responde(monkeypatch):
    principal = _ChatModelFalso(contenido='{"titulo": "Índices", "items": []}')
    respaldo = _ChatModelFalso(contenido='{"titulo": "Otro", "items": []}')
    provider = _crear_provider_con_respaldo(monkeypatch, principal, respaldo)

    resultado = provider.generate_structured(
        [HumanMessage(content="hola")], _RespuestaPrueba
    )

    assert resultado.titulo == "Índices"
    assert principal.invocaciones == 1
    assert respaldo.invocaciones == 0


def test_si_fallan_ambos_modelos_mantiene_error_del_proveedor(monkeypatch):
    principal = _ChatModelFalso(excepcion=_error_api(429, "RESOURCE_EXHAUSTED"))
    respaldo = _ChatModelFalso(excepcion=_error_api(503, "UNAVAILABLE"))
    provider = _crear_provider_con_respaldo(monkeypatch, principal, respaldo)

    with pytest.raises(LLMProviderError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)

    assert principal.invocaciones == respaldo.invocaciones == 1


@pytest.mark.parametrize(
    "excepcion",
    [_error_api(401, "UNAUTHENTICATED"), TimeoutError("timeout")],
)
def test_otros_errores_no_activan_respaldo(monkeypatch, excepcion):
    principal = _ChatModelFalso(excepcion=excepcion)
    respaldo = _ChatModelFalso(contenido='{"titulo": "Índices", "items": []}')
    provider = _crear_provider_con_respaldo(monkeypatch, principal, respaldo)

    with pytest.raises(LLMProviderError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)

    assert principal.invocaciones == 1
    assert respaldo.invocaciones == 0


def test_respuesta_fuera_de_esquema_no_activa_respaldo(monkeypatch):
    principal = _ChatModelFalso(contenido="esto no es JSON")
    respaldo = _ChatModelFalso(contenido='{"titulo": "Índices", "items": []}')
    provider = _crear_provider_con_respaldo(monkeypatch, principal, respaldo)

    with pytest.raises(LLMProviderError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)

    assert principal.invocaciones == 1
    assert respaldo.invocaciones == 0


def test_sin_respaldo_configurado_no_crea_otro_modelo(monkeypatch):
    modelos_creados = []

    def _fabrica(**kwargs):
        modelos_creados.append(kwargs["model"])
        return _ChatModelFalso(excepcion=_error_api(503, "UNAVAILABLE"))

    monkeypatch.setattr(gemini_provider_module, "ChatGoogleGenerativeAI", _fabrica)
    provider = GeminiProvider(
        model="modelo-principal", fallback_model=" ",
        api_key="fake-key-no-real", timeout=1.0,
    )

    with pytest.raises(LLMProviderError):
        provider.generate_structured([HumanMessage(content="hola")], _RespuestaPrueba)

    assert modelos_creados == ["modelo-principal"]


def test_respaldo_debe_ser_distinto_del_principal(monkeypatch):
    monkeypatch.setattr(
        gemini_provider_module, "ChatGoogleGenerativeAI", lambda **_kwargs: _ChatModelFalso(),
    )
    with pytest.raises(ValueError, match="distinto"):
        GeminiProvider(
            model="modelo-principal", fallback_model="modelo-principal",
            api_key="fake-key-no-real", timeout=1.0,
        )
