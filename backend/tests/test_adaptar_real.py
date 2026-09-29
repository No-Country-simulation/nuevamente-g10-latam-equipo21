"""Tests de NM-12: orquestador, errores, request id y adaptador de contexto (con fakes)."""
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.schemas.content import FlashcardItem
from app.schemas.output import (
    AlmacenamientoOCISchema, ContenidoAdaptadoSchema,
    EvaluacionCalidadSchema, MetadatosSchema,
)
from app.services.adaptacion_adapters import (
    ContextoRealAdapter, VerificadorRealAdapter, documento_id_desde_contenido,
)
from app.services.adaptacion_service import AdaptacionService, ContextoRecuperado, FuenteContexto
from app.services.dependencies import get_adaptacion_service

URL = "/api/v1/adaptar-contenido"
PAYLOAD = {
    "documento_titulo": "Redes VCN en OCI",
    "documento_contenido": "La VCN es una red privada configurable en Oracle Cloud.",
    "perfil_destinatario": "Principiante",
    "formato_salida": "Flashcards",
    "nicho_sector": "General",
    "nivel_detalle": "Didactico",
}
SECRETO = "sk-SECRETO-NO-DEBE-SALIR"


class FakeContexto:
    def __init__(self, texto="contexto relevante", error=None):
        self.texto, self.error = texto, error
    def obtener_contexto(self, payload):
        if self.error: raise self.error
        return ContextoRecuperado(self.texto, [FuenteContexto("c1", 1, 0.9)])

class FakeGenerador:
    def __init__(self, error=None): self.error = error
    def generar(self, payload, contexto):
        if self.error: raise self.error
        return ContenidoAdaptadoSchema(
            titulo="T", introduccion_contextualizada="I",
            items=[FlashcardItem(frente="f", dorso="d", pista_didactica="p")])

class FakeVerificador:
    def evaluar(self, payload, contenido, contexto):
        return EvaluacionCalidadSchema(anclaje_fuente_score=0.9, claridad_pedagogica="Alta", observaciones="ok")

class FakeMetadatos:
    def generar(self, payload, contenido):
        return MetadatosSchema(perfil_aplicado=payload.perfil_destinatario,
                               formato_generado=payload.formato_salida,
                               tiempo_estimado_estudio_minutos=5, conceptos_clave=["VCN"])

class FakeStorage:
    def __init__(self, error=None): self.error = error
    def guardar(self, payload, paquete):
        if self.error: raise self.error
        return AlmacenamientoOCISchema(bucket="b", objeto_id="o/1.json", status_upload="completado")


def make_client(**over):
    parts = dict(contexto=FakeContexto(), generador=FakeGenerador(), verificador=FakeVerificador(),
                 metadatos=FakeMetadatos(), storage=FakeStorage())
    parts.update(over)
    app = create_app()
    app.dependency_overrides[get_adaptacion_service] = lambda: AdaptacionService(**parts)
    return TestClient(app, raise_server_exceptions=False), app


def test_200_con_los_cuatro_bloques():
    c, _ = make_client()
    r = c.post(URL, json=PAYLOAD)
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "exito"
    for k in ("metadatos", "contenido_adaptado", "evaluacion_calidad", "almacenamiento_oci"):
        assert k in b
    assert b["almacenamiento_oci"]["status_upload"] == "completado"


def test_422_campo_faltante():
    c, _ = make_client()
    p = dict(PAYLOAD); del p["nicho_sector"]
    r = c.post(URL, json=p)
    assert r.status_code == 422
    assert r.json()["status"] == "error" and "nicho_sector" in r.json()["error"]["mensaje"]


def test_422_enum_lista_valores_validos():
    c, _ = make_client()
    r = c.post(URL, json={**PAYLOAD, "perfil_destinatario": "Marciano"})
    assert r.status_code == 422
    m = r.json()["error"]["mensaje"]
    assert "perfil_destinatario" in m and "Principiante" in m and "Gestor_Ejecutivo_No_Tecnico" in m


@pytest.mark.parametrize("parte,codigo", [
    ("generador", "LLM_NO_DISPONIBLE"),
    ("contexto", "VECTOR_STORE_NO_DISPONIBLE"),
])
def test_502_sin_filtrar_internos(parte, codigo):
    err = RuntimeError(f"boom api_key={SECRETO}")
    obj = FakeGenerador(err) if parte == "generador" else FakeContexto(error=err)
    c, _ = make_client(**{parte: obj})
    r = c.post(URL, json=PAYLOAD)
    assert r.status_code == 502
    assert r.json()["error"]["codigo"] == codigo
    assert SECRETO not in r.text and "Traceback" not in r.text and "boom" not in r.text


def test_oci_falla_no_invalida_respuesta():
    c, _ = make_client(storage=FakeStorage(error=RuntimeError("oci down")))
    r = c.post(URL, json=PAYLOAD)
    assert r.status_code == 200
    assert r.json()["almacenamiento_oci"]["status_upload"] == "error"
    assert r.json()["contenido_adaptado"]["items"]


def test_sin_contexto_no_llama_al_llm():
    gen = FakeGenerador(error=AssertionError("no debe llamarse"))
    c, _ = make_client(contexto=FakeContexto(texto="  "), generador=gen)
    r = c.post(URL, json=PAYLOAD)
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "SIN_CONTEXTO_RELEVANTE"


def test_request_id_en_header_y_log(caplog):
    c, _ = make_client(generador=FakeGenerador(RuntimeError("x")))
    with caplog.at_level(logging.ERROR):
        r = c.post(URL, json=PAYLOAD, headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
    assert any("abc123" in rec.getMessage() for rec in caplog.records)
    assert "X-Request-ID" in c.post(URL, json=PAYLOAD).headers


def test_error_no_controlado_devuelve_500_con_shape(caplog):
    c, app = make_client()
    @app.get("/boom")
    def boom(): raise ValueError(SECRETO)
    with caplog.at_level(logging.ERROR):
        r = c.get("/boom")
    assert r.status_code == 500 and r.json()["error"]["codigo"] == "ERROR_INTERNO"
    assert SECRETO not in r.text
    assert any("ERROR_INTERNO" in rec.getMessage() for rec in caplog.records)


def test_flag_mock_y_501_sin_cablear(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_LLM", True)
    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.post(URL, json=PAYLOAD)
    assert r.status_code == 200 and "MOCK" in r.json()["evaluacion_calidad"]["observaciones"]
    monkeypatch.setattr(settings, "USE_MOCK_LLM", False)
    r = c.post(URL, json=PAYLOAD)
    assert r.status_code == 501 and r.json()["error"]["codigo"] == "PIPELINE_NO_CONFIGURADA"


# --- ContextoRealAdapter con fakes de NM-05/06 ---
class FakeChroma:
    def __init__(self, existentes=0): self.n, self.indexados = existentes, []
    def count_document(self, document_id): return self.n
    def index_chunks(self, chunks): self.indexados.append(chunks); return len(chunks)

def _adapter(chroma, fragmentos):
    llamadas = {}
    def chunker(document_id, pages): llamadas["c"] = (document_id, pages); return ["chunk"]
    def recuperar(*, consulta, vector_store, documento_id=None):
        llamadas["r"] = (consulta, documento_id); return fragmentos
    a = ContextoRealAdapter(chroma_store=chroma, vector_store="vs", chunker=chunker,
                            recuperar=recuperar, ensamblar=lambda f: "TEXTO " + str(len(f)))
    return a, llamadas

def _payload():
    return SimpleNamespace(documento_titulo="Titulo", documento_contenido="contenido largo " * 5)

def test_contexto_indexa_si_no_existe_y_arma_fuentes():
    frag = SimpleNamespace(chunk_id="c9", score=0.8, metadatos={"page_number": 3})
    chroma = FakeChroma(0)
    a, ll = _adapter(chroma, [frag])
    ctx = a.obtener_contexto(_payload())
    assert chroma.indexados and ll["c"][1] == [{"page_number": 1, "text": _payload().documento_contenido}]
    assert ctx.texto == "TEXTO 1" and ctx.fuentes[0].pagina == 3
    assert ll["r"][1] == documento_id_desde_contenido(_payload().documento_contenido)

def test_contexto_no_reindexa_si_ya_existe_y_vacio_sin_fragmentos():
    chroma = FakeChroma(4)
    a, _ = _adapter(chroma, [])
    ctx = a.obtener_contexto(_payload())
    assert chroma.indexados == [] and ctx.texto == ""


# --- VerificadorRealAdapter (NM-09) con fake ---
def test_verificador_pasa_doc_id_y_vector_store_compartidos():
    chroma = FakeChroma(1)
    ctx_adapter, _ = _adapter(chroma, [])
    visto = {}
    def evaluar(**kw):
        visto.update(kw)
        return EvaluacionCalidadSchema(anclaje_fuente_score=0.75, claridad_pedagogica="Media", observaciones="ok")
    v = VerificadorRealAdapter(ctx_adapter, llm_provider="LLM", evaluar=evaluar)
    p = SimpleNamespace(documento_contenido="contenido largo " * 5,
                        perfil_destinatario=SimpleNamespace(value="Principiante"))
    res = v.evaluar(p, "CONTENIDO", None)
    assert res.anclaje_fuente_score == 0.75
    assert visto["documento_id"] == documento_id_desde_contenido(p.documento_contenido)
    assert visto["vector_store"] == "vs" and visto["llm_provider"] == "LLM"
    assert visto["contenido_adaptado"] == "CONTENIDO" and visto["perfil_destinatario"] == "Principiante"
