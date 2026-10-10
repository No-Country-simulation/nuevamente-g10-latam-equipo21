"""Tests de NM-28: servicio multi-agente y selección por USE_MULTIAGENT."""

import pytest

from app.core.errors import LLMError, SinContextoRelevanteError
from app.schemas.input import InputSchema
from app.schemas.output import AlmacenamientoOCISchema, EvaluacionCalidadSchema
from app.services.adaptacion_multiagente_service import AdaptacionMultiAgenteService
from app.services.adaptacion_service import ContextoRecuperado, FuenteContexto
from app.services.mock_adaptacion_service import construir_respuesta_mock


def _payload() -> InputSchema:
    return InputSchema(
        documento_titulo="Introduccion a la Arquitectura de Redes VCN en OCI",
        documento_contenido="La Virtual Cloud Network (VCN) es una red privada en OCI.",
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Didactico",
    )


class _FakeContexto:
    def __init__(self, texto="fragmento relevante"):
        self.texto = texto
        self.llamadas = 0

    def obtener_contexto(self, payload):
        self.llamadas += 1
        return ContextoRecuperado(
            texto=self.texto, fuentes=[FuenteContexto(chunk_id="c1", pagina=1, score=0.9)]
        )


class _FakeMetadatos:
    def __init__(self, metadatos):
        self._metadatos = metadatos

    def generar(self, payload, contenido):
        return self._metadatos


class _FakeStorage:
    def __init__(self, falla=False):
        self.falla = falla
        self.paquetes = []

    def guardar(self, payload, paquete):
        if self.falla:
            raise RuntimeError("OCI caído")
        self.paquetes.append(paquete)
        return AlmacenamientoOCISchema(
            bucket="b", objeto_id="obj.json", status_upload="completado"
        )


class _FakeGrafo:
    def __init__(self, estado=None, error=None):
        self.estado = estado
        self.error = error
        self.recibido = None

    def invoke(self, estado_inicial):
        self.recibido = estado_inicial
        if self.error:
            raise self.error
        return self.estado


def _servicio(grafo, contexto=None, storage=None):
    base = construir_respuesta_mock(_payload())
    return AdaptacionMultiAgenteService(
        contexto=contexto or _FakeContexto(),
        metadatos=_FakeMetadatos(base.metadatos),
        storage=storage or _FakeStorage(),
        grafo=grafo,
    ), base


def _estado_final(base, score=0.9):
    return {
        "contenido_adaptado": base.contenido_adaptado,
        "evaluacion_calidad": EvaluacionCalidadSchema(
            anclaje_fuente_score=score,
            claridad_pedagogica="Alta",
            observaciones="ok",
        ),
        "iteracion": 2,
    }


def test_devuelve_output_schema_con_lo_que_produjo_el_grafo():
    base = construir_respuesta_mock(_payload())
    grafo = _FakeGrafo(estado=_estado_final(base, score=0.85))
    servicio, _ = _servicio(grafo)

    respuesta = servicio.adaptar(_payload())

    assert respuesta.status == "exito"
    assert respuesta.evaluacion_calidad.anclaje_fuente_score == 0.85
    assert respuesta.almacenamiento_oci.status_upload == "completado"


def test_el_estado_inicial_trae_el_contexto_ya_recuperado_y_los_parametros():
    base = construir_respuesta_mock(_payload())
    grafo = _FakeGrafo(estado=_estado_final(base))
    contexto = _FakeContexto(texto="contexto por ventanas")
    servicio, _ = _servicio(grafo, contexto=contexto)

    servicio.adaptar(_payload())

    assert grafo.recibido["contexto_recuperado"] == "contexto por ventanas"
    assert grafo.recibido["perfil_destinatario"] == "Principiante"
    assert grafo.recibido["formato_salida"] == "Flashcards"
    assert grafo.recibido["documento_id"].startswith("doc-")
    assert contexto.llamadas == 1


def test_sin_contexto_no_invoca_el_grafo():
    grafo = _FakeGrafo(estado={})
    servicio, _ = _servicio(grafo, contexto=_FakeContexto(texto="   "))

    with pytest.raises(SinContextoRelevanteError):
        servicio.adaptar(_payload())

    assert grafo.recibido is None


def test_falla_del_grafo_se_traduce_a_llm_error():
    grafo = _FakeGrafo(error=RuntimeError("langgraph interno"))
    servicio, _ = _servicio(grafo)

    with pytest.raises(LLMError):
        servicio.adaptar(_payload())


def test_falla_de_oci_no_invalida_la_respuesta():
    base = construir_respuesta_mock(_payload())
    grafo = _FakeGrafo(estado=_estado_final(base))
    servicio, _ = _servicio(grafo, storage=_FakeStorage(falla=True))

    respuesta = servicio.adaptar(_payload())

    assert respuesta.almacenamiento_oci.status_upload == "error"


def test_score_bajo_llega_a_evaluacion_calidad_sin_fallar():
    """Agotadas las iteraciones, el grafo devuelve el mejor resultado: no es un error."""
    base = construir_respuesta_mock(_payload())
    grafo = _FakeGrafo(estado=_estado_final(base, score=0.4))
    servicio, _ = _servicio(grafo)

    respuesta = servicio.adaptar(_payload())

    assert respuesta.status == "exito"
    assert respuesta.evaluacion_calidad.anclaje_fuente_score == 0.4


def test_el_flag_selecciona_el_servicio_multiagente(monkeypatch):
    from app.services import dependencies

    monkeypatch.setattr(dependencies.settings, "USE_MOCK_LLM", False)
    monkeypatch.setattr(dependencies.settings, "USE_MULTIAGENT", True)
    sentinela_multi, sentinela_lineal = object(), object()
    monkeypatch.setattr(dependencies, "construir_servicio_multiagente", lambda: sentinela_multi)
    monkeypatch.setattr(dependencies, "construir_servicio_real", lambda: sentinela_lineal)

    assert dependencies.get_adaptacion_service() is sentinela_multi


def test_flag_apagado_sigue_el_camino_lineal(monkeypatch):
    from app.services import dependencies

    monkeypatch.setattr(dependencies.settings, "USE_MOCK_LLM", False)
    monkeypatch.setattr(dependencies.settings, "USE_MULTIAGENT", False)
    sentinela_multi, sentinela_lineal = object(), object()
    monkeypatch.setattr(dependencies, "construir_servicio_multiagente", lambda: sentinela_multi)
    monkeypatch.setattr(dependencies, "construir_servicio_real", lambda: sentinela_lineal)

    assert dependencies.get_adaptacion_service() is sentinela_lineal


def test_el_mock_tiene_prioridad_sobre_el_flag(monkeypatch):
    from app.services import dependencies

    monkeypatch.setattr(dependencies.settings, "USE_MOCK_LLM", True)
    monkeypatch.setattr(dependencies.settings, "USE_MULTIAGENT", True)

    assert isinstance(dependencies.get_adaptacion_service(), dependencies.MockAdaptacionService)