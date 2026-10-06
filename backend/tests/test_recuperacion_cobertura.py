"""Tests de NM-22: la recuperación cubre el documento completo."""
from types import SimpleNamespace

from app.core.config import settings
from app.services.adaptacion_adapters import (
    ContextoRealAdapter,
    calcular_num_ventanas,
    construir_consultas,
    dividir_en_ventanas,
)


class FakeChroma:
    def count_document(self, document_id):
        return 1  # ya indexado: estos tests no ejercitan el chunker

    def index_chunks(self, chunks):
        return len(chunks)


def _documento_largo(secciones: int = 5, largo: int = 6000) -> str:
    """Documento con un marcador distinto al inicio de cada sección."""
    return "".join(f"SECCION{i} ".ljust(largo, "x") for i in range(secciones))


def _adapter(respuestas):
    """`respuestas`: función (consulta, top_k) -> lista de fragmentos."""
    llamadas = []

    def recuperar(*, consulta, vector_store, documento_id=None, **kwargs):
        llamadas.append({"consulta": consulta, "kwargs": kwargs})
        return respuestas(consulta, kwargs.get("top_k"))

    adapter = ContextoRealAdapter(
        chroma_store=FakeChroma(),
        vector_store="vs",
        chunker=lambda **_: [],
        recuperar=recuperar,
        ensamblar=lambda frs: "|".join(f.chunk_id for f in frs),
    )
    return adapter, llamadas


def _frag(chunk_id):
    return SimpleNamespace(chunk_id=chunk_id, score=0.9, metadatos={})


def _payload(contenido):
    return SimpleNamespace(documento_titulo="Titulo", documento_contenido=contenido)


# --- calcular_num_ventanas / división ---
def test_documento_corto_usa_una_ventana():
    assert calcular_num_ventanas(10) == 1
    assert calcular_num_ventanas(settings.RETRIEVAL_VENTANA_CHARS) == 1


def test_ventanas_crecen_con_el_largo_y_tienen_tope():
    assert calcular_num_ventanas(settings.RETRIEVAL_VENTANA_CHARS + 1) == 2
    assert calcular_num_ventanas(10_000_000) == settings.RETRIEVAL_MAX_VENTANAS


def test_dividir_en_ventanas_cubre_todo_el_texto():
    texto = _documento_largo()
    partes = dividir_en_ventanas(texto, 5)
    assert len(partes) == 5
    assert "".join(partes) == texto


def test_consultas_corto_es_la_consulta_original():
    assert construir_consultas("T", "hola") == ["T\nhola"]


# --- comportamiento del adaptador ---
def test_documento_corto_no_cambia_el_llamado():
    adapter, llamadas = _adapter(lambda c, k: [_frag("c1")])
    ctx = adapter.obtener_contexto(_payload("contenido corto " * 5))
    assert len(llamadas) == 1
    assert llamadas[0]["kwargs"] == {}  # sin top_k: idéntico al comportamiento previo
    assert ctx.texto == "c1"


def test_documento_largo_consulta_cada_seccion():
    def respuestas(consulta, top_k):
        for i in range(5):
            if f"SECCION{i}" in consulta:
                return [_frag(f"c{i}")]
        return []

    adapter, llamadas = _adapter(respuestas)
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert len(llamadas) == settings.RETRIEVAL_MAX_VENTANAS
    # fragmentos de todas las secciones, en orden de documento
    assert ctx.texto == "c0|c1|c2|c3|c4"


def test_contenido_clave_al_final_llega_al_contexto():
    # 30000 caracteres: la última sección (desde el 24000) empieza con el tema final.
    documento = "x" * 24000 + "TEMA_FINAL " + "y" * 5989
    assert len(documento) == 30000

    def respuestas(consulta, top_k):
        return [_frag("final")] if "TEMA_FINAL" in consulta else [_frag("inicio")]

    adapter, _ = _adapter(respuestas)
    ctx = adapter.obtener_contexto(_payload(documento))
    assert "final" in ctx.texto.split("|")


def test_deduplica_por_chunk_id():
    adapter, _ = _adapter(lambda c, k: [_frag("mismo")])
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert ctx.texto == "mismo"


def test_top_k_se_reparte_y_el_total_queda_acotado():
    contador = {"n": 0}

    def respuestas(consulta, top_k):
        base = contador["n"]
        contador["n"] += top_k
        return [_frag(f"c{base + j}") for j in range(top_k)]

    adapter, llamadas = _adapter(respuestas)
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    ventanas = len(llamadas)
    por_ventana = max(1, settings.RETRIEVAL_TOP_K // ventanas)
    assert all(l["kwargs"]["top_k"] == por_ventana for l in llamadas)
    assert len(ctx.texto.split("|")) <= max(settings.RETRIEVAL_TOP_K, ventanas)


def test_ventana_sin_resultados_no_rompe():
    adapter, _ = _adapter(lambda c, k: [])
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert ctx.texto == "" and ctx.fuentes == []