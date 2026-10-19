"""Tests de NM-22: la recuperación cubre el documento completo."""
from types import SimpleNamespace
import logging
from types import SimpleNamespace

from app.core.config import settings
from app.services.adaptacion_adapters import (
    ContextoRealAdapter,
    calcular_num_ventanas,
    construir_consultas,
    dividir_en_ventanas,
)


class FakeChroma:
    def __init__(self, total=1):
        self.total = total

    def count_document(self, document_id):
        return self.total  # ya indexado: estos tests no ejercitan el chunker

    def index_chunks(self, chunks):
        return len(chunks)


def _documento_largo(secciones: int = 5, largo: int = 6000) -> str:
    """Documento con un marcador distinto al inicio de cada sección."""
    return "".join(f"SECCION{i} ".ljust(largo, "x") for i in range(secciones))


def _adapter(respuestas, total_chunks=1):
    """`respuestas`: función (consulta, top_k) -> lista de fragmentos."""
    llamadas = []

    def recuperar(*, consulta, vector_store, documento_id=None, **kwargs):
        llamadas.append({"consulta": consulta, "kwargs": kwargs})
        return respuestas(consulta, kwargs.get("top_k"))

    adapter = ContextoRealAdapter(
        chroma_store=FakeChroma(total_chunks),
        vector_store="vs",
        chunker=lambda **_: [],
        recuperar=recuperar,
        ensamblar=lambda frs: "|".join(f.chunk_id for f in frs),
    )
    return adapter, llamadas


def _frag(chunk_id, indice=None):
    metadatos = {} if indice is None else {"chunk_index": indice}
    return SimpleNamespace(chunk_id=chunk_id, score=0.9, metadatos=metadatos)


def _respuestas_por_ventana(total, ancho):
    """Ranking simulado que respeta top_k.

    En la llamada i devuelve top_k chunks centrados en la ventana i, por lo que
    incluye vecinos de otras zonas, como haria una busqueda por similitud real.
    """
    estado = {"i": 0}

    def respuestas(consulta, top_k):
        i = estado["i"]
        estado["i"] += 1
        inicio = max(0, i * ancho - (top_k - ancho) // 2)
        fin = min(total, inicio + top_k)
        return [_frag(f"c{j}", j) for j in range(inicio, fin)]

    return respuestas


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


def test_pide_candidatos_y_el_total_queda_acotado():
    contador = {"n": 0}

    def respuestas(consulta, top_k):
        base = contador["n"]
        contador["n"] += top_k
        return [_frag(f"c{base + j}") for j in range(top_k)]

    adapter, llamadas = _adapter(respuestas)
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    ventanas = len(llamadas)
    previo = max(1, settings.RETRIEVAL_TOP_K // ventanas)
    candidatos = max(settings.RETRIEVAL_VENTANA_CANDIDATOS, previo)
    assert all(l["kwargs"]["top_k"] == candidatos for l in llamadas)
    # sin chunk_index se usa el comportamiento previo: `previo` por ventana
    assert len(ctx.texto.split("|")) <= ventanas * max(
        settings.RETRIEVAL_FRAGMENTOS_POR_VENTANA, previo
    )


def test_ventana_sin_resultados_no_rompe():
    adapter, _ = _adapter(lambda c, k: [])
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert ctx.texto == "" and ctx.fuentes == []


def test_filtra_por_rango_de_chunk_index(monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    monkeypatch.setattr(settings, "RETRIEVAL_VENTANA_CANDIDATOS", 8)
    monkeypatch.setattr(settings, "RETRIEVAL_FRAGMENTOS_POR_VENTANA", 2)
    # 40 chunks y 10 ventanas: la ventana i cubre los indices [4i, 4i+4).
    # El fake respeta top_k (8) y devuelve tambien vecinos de otras ventanas.
    adapter, llamadas = _adapter(
        _respuestas_por_ventana(total=40, ancho=4), total_chunks=40
    )
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert len(llamadas) == 10
    assert all(l["kwargs"]["top_k"] == 8 for l in llamadas)
    esperado = [f"c{4 * i + d}" for i in range(10) for d in (0, 1)]
    assert ctx.texto.split("|") == esperado


def test_con_indices_fuera_de_la_ventana_no_aporta_nada(monkeypatch, caplog):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    adapter, llamadas = _adapter(
        lambda c, k: [_frag("x", 999)][:k], total_chunks=40
    )
    with caplog.at_level(logging.WARNING, logger="nuevamente.adaptacion"):
        ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert len(llamadas) == 10
    assert ctx.texto == "" and ctx.fuentes == []
    avisos = [r for r in caplog.records if "sin candidatos en el rango" in r.getMessage()]
    assert len(avisos) == 10


def test_ventana_sin_candidatos_en_rango_no_rellena_con_otras_zonas(monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    monkeypatch.setattr(settings, "RETRIEVAL_VENTANA_CANDIDATOS", 8)
    monkeypatch.setattr(settings, "RETRIEVAL_FRAGMENTOS_POR_VENTANA", 1)
    # Todas las ventanas reciben solo chunks 0..7: unicamente las ventanas 0 y 1
    # (rangos [0,4) y [4,8)) tienen candidatos propios; el resto debe quedar vacio.
    adapter, _ = _adapter(
        lambda c, k: [_frag(f"c{j}", j) for j in range(8)][:k], total_chunks=40
    )
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    assert ctx.texto.split("|") == ["c0", "c4"]


def test_sin_chunk_index_usa_el_comportamiento_previo(monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    monkeypatch.setattr(settings, "RETRIEVAL_TOP_K", 20)  # previo = 20 // 10 = 2
    adapter, _ = _adapter(
        lambda c, k: [_frag(f"s{j}") for j in range(20)][:k], total_chunks=40
    )
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    # sin chunk_index, cada ventana toma los primeros 2 y se deduplican
    assert ctx.texto.split("|") == ["s0", "s1"]