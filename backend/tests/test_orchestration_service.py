"""
Tests de orquestación (NM-08) usando un doble de prueba de LLMProvider, exclusivo de esta
suite. No debe convertirse en un contrato productivo: es un fake local a tests/.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import BaseMessage

from app.services.llm_provider import LLMProviderError, LLMTimeoutError
from app.services.orchestration_service import generar_contenido_adaptado


class _ProveedorFalso:
    def __init__(
        self,
        *,
        respuesta: dict[str, Any] | None = None,
        excepcion: Exception | None = None,
    ) -> None:
        self._respuesta = respuesta
        self._excepcion = excepcion
        self.ultimos_mensajes: list[BaseMessage] | None = None

    def generate_json(self, messages: list[BaseMessage]) -> dict[str, Any]:
        self.ultimos_mensajes = messages
        if self._excepcion is not None:
            raise self._excepcion
        assert self._respuesta is not None
        return self._respuesta


def _parametros_base(**overrides: Any) -> dict[str, Any]:
    base = dict(
        documento_titulo="Índices en bases de datos",
        contexto_recuperado="CONTEXTO-UNICO-DE-PRUEBA",
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Introductorio",
    )
    base.update(overrides)
    return base


def test_devuelve_el_json_generado_por_el_proveedor():
    proveedor = _ProveedorFalso(respuesta={"titulo": "X", "items": []})
    resultado = generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)
    assert resultado == {"titulo": "X", "items": []}


def test_propaga_timeout_como_error_tipado_sin_colgarse():
    proveedor = _ProveedorFalso(excepcion=LLMTimeoutError("timeout simulado"))
    with pytest.raises(LLMTimeoutError):
        generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)


def test_propaga_fallo_generico_del_proveedor_como_error_tipado():
    proveedor = _ProveedorFalso(excepcion=LLMProviderError("fallo simulado"))
    with pytest.raises(LLMProviderError):
        generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)


def test_el_contexto_recuperado_llega_intacto_al_proveedor_como_dato_opaco():
    proveedor = _ProveedorFalso(respuesta={})
    generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)
    assert proveedor.ultimos_mensajes is not None
    contenido = "\n".join(m.content for m in proveedor.ultimos_mensajes)
    assert "CONTEXTO-UNICO-DE-PRUEBA" in contenido


def test_perfiles_distintos_generan_mensajes_distintos_hacia_el_proveedor():
    proveedor_a = _ProveedorFalso(respuesta={})
    proveedor_b = _ProveedorFalso(respuesta={})
    generar_contenido_adaptado(
        **_parametros_base(perfil_destinatario="Principiante"), llm_provider=proveedor_a
    )
    generar_contenido_adaptado(
        **_parametros_base(perfil_destinatario="Lider_Tecnico_Arquitecto"),
        llm_provider=proveedor_b,
    )
    assert proveedor_a.ultimos_mensajes[1].content != proveedor_b.ultimos_mensajes[1].content


def test_formatos_distintos_generan_mensajes_distintos_hacia_el_proveedor():
    proveedor_a = _ProveedorFalso(respuesta={})
    proveedor_b = _ProveedorFalso(respuesta={})
    generar_contenido_adaptado(
        **_parametros_base(formato_salida="Flashcards"), llm_provider=proveedor_a
    )
    generar_contenido_adaptado(
        **_parametros_base(formato_salida="Quiz"), llm_provider=proveedor_b
    )
    assert proveedor_a.ultimos_mensajes[1].content != proveedor_b.ultimos_mensajes[1].content


def test_devuelve_dict_generico_sin_validar_contra_schema_de_contenido_adaptado():
    """
    NM-08 no valida el resultado contra el contrato estricto de contenido_adaptado (NM-07,
    pendiente de integración): un dict con forma arbitraria se devuelve tal cual.
    """
    proveedor = _ProveedorFalso(respuesta={"cualquier_clave": "cualquier_valor"})
    resultado = generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)
    assert resultado == {"cualquier_clave": "cualquier_valor"}
