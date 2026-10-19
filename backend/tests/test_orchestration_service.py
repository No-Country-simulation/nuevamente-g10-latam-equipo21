"""
Tests de orquestación (NM-08) usando un doble de prueba de LLMProvider, exclusivo de esta
suite. No debe convertirse en un contrato productivo: es un fake local a tests/.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.schemas.content import FlashcardItem, QuizItem, TutorialItem
from app.schemas.output import ContenidoAdaptadoSchema
from app.services.llm_provider import LLMProviderError, LLMTimeoutError
from app.services.orchestration_service import (
    ContenidoAdaptadoInvalidoError,
    generar_contenido_adaptado,
)


class _ProveedorFalso:
    def __init__(
        self,
        *,
        respuesta: BaseModel | None = None,
        excepcion: Exception | None = None,
    ) -> None:
        self._respuesta = respuesta
        self._excepcion = excepcion
        self.ultimos_mensajes: list[BaseMessage] | None = None

    def generate_structured(
        self,
        messages: list[BaseMessage],
        schema: type[BaseModel],
    ) -> BaseModel:
        self.ultimos_mensajes = messages
        if self._excepcion is not None:
            raise self._excepcion
        assert self._respuesta is not None
        assert isinstance(self._respuesta, schema)
        return self._respuesta


def _contenido_flashcards() -> ContenidoAdaptadoSchema:
    return ContenidoAdaptadoSchema(
        titulo="Índices",
        introduccion_contextualizada="Introducción",
        items=[
            FlashcardItem(
                frente="¿Qué es un índice?",
                dorso="Una estructura de búsqueda.",
                pista_didactica="Pensalo como el índice de un libro.",
            )
        ],
    )


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


def test_devuelve_el_contenido_validado_generado_por_el_proveedor():
    contenido = _contenido_flashcards()
    proveedor = _ProveedorFalso(respuesta=contenido)
    resultado = generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)
    assert resultado == contenido


def test_propaga_timeout_como_error_tipado_sin_colgarse():
    proveedor = _ProveedorFalso(excepcion=LLMTimeoutError("timeout simulado"))
    with pytest.raises(LLMTimeoutError):
        generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)


def test_propaga_fallo_generico_del_proveedor_como_error_tipado():
    proveedor = _ProveedorFalso(excepcion=LLMProviderError("fallo simulado"))
    with pytest.raises(LLMProviderError):
        generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)


def test_el_contexto_recuperado_llega_intacto_al_proveedor_como_dato_opaco():
    proveedor = _ProveedorFalso(respuesta=_contenido_flashcards())
    generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)
    assert proveedor.ultimos_mensajes is not None
    contenido = "\n".join(m.content for m in proveedor.ultimos_mensajes)
    assert "CONTEXTO-UNICO-DE-PRUEBA" in contenido


def test_perfiles_distintos_generan_mensajes_distintos_hacia_el_proveedor():
    proveedor_a = _ProveedorFalso(respuesta=_contenido_flashcards())
    proveedor_b = _ProveedorFalso(respuesta=_contenido_flashcards())
    generar_contenido_adaptado(
        **_parametros_base(perfil_destinatario="Principiante"), llm_provider=proveedor_a
    )
    generar_contenido_adaptado(
        **_parametros_base(perfil_destinatario="Lider_Tecnico_Arquitecto"),
        llm_provider=proveedor_b,
    )
    assert proveedor_a.ultimos_mensajes[1].content != proveedor_b.ultimos_mensajes[1].content


def test_formatos_distintos_generan_mensajes_distintos_hacia_el_proveedor():
    proveedor_a = _ProveedorFalso(respuesta=_contenido_flashcards())
    proveedor_b = _ProveedorFalso(
        respuesta=ContenidoAdaptadoSchema(
            titulo="Quiz",
            introduccion_contextualizada="Introducción",
            items=[
                QuizItem(
                    pregunta="¿Qué es un índice?",
                    opciones=["A", "B", "C", "D"],
                    respuesta_correcta="A",
                    justificacion="Porque sí.",
                )
            ],
        )
    )
    generar_contenido_adaptado(
        **_parametros_base(formato_salida="Flashcards"), llm_provider=proveedor_a
    )
    generar_contenido_adaptado(
        **_parametros_base(formato_salida="Quiz"), llm_provider=proveedor_b
    )
    assert proveedor_a.ultimos_mensajes[1].content != proveedor_b.ultimos_mensajes[1].content


def test_rechaza_items_que_no_corresponden_al_formato_solicitado():
    contenido = ContenidoAdaptadoSchema(
        titulo="Mezcla inválida",
        introduccion_contextualizada="Introducción",
        items=[
            FlashcardItem(frente="F", dorso="D", pista_didactica="P"),
            TutorialItem(
                paso_numero=1,
                titulo_paso="Paso",
                contenido="Contenido",
                codigo_ejemplo=None,
            ),
        ],
    )
    proveedor = _ProveedorFalso(respuesta=contenido)

    with pytest.raises(ContenidoAdaptadoInvalidoError, match=r"posiciones \[1\]"):
        generar_contenido_adaptado(**_parametros_base(), llm_provider=proveedor)
