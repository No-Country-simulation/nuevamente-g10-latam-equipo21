"""Tests de NM-22: la recuperación cubre el documento completo."""

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


def _frag(chunk_id, indice=None, texto=None):
    metadatos = {} if indice is None else {"chunk_index": indice}
    return SimpleNamespace(
        chunk_id=chunk_id,
        documento_id="doc",
        score=0.9,
        metadatos=metadatos,
        texto=texto if texto is not None else f"texto {chunk_id}",
    )


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
    # Cada ventana conserva todos los chunks de su rango (cupo proporcional, NM-33).
    esperado = [f"c{i}" for i in range(40)]
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
    monkeypatch.setattr(settings, "RETRIEVAL_FRAGMENTOS_POR_VENTANA", 1) # piso; el cupo real es proporcional al rango
    # Todas las ventanas reciben solo chunks 0..7: unicamente las ventanas 0 y 1
    # (rangos [0,4) y [4,8)) tienen candidatos propios; el resto debe quedar vacio.
    adapter, _ = _adapter(
        lambda c, k: [_frag(f"c{j}", j) for j in range(8)][:k], total_chunks=40
    )
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    # Las ventanas 0 y 1 conservan los 4 chunks de su rango cada una.
    assert ctx.texto.split("|") == ["c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7"]


def test_sin_chunk_index_usa_el_comportamiento_previo(monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    monkeypatch.setattr(settings, "RETRIEVAL_TOP_K", 20)  # previo = 20 // 10 = 2
    adapter, _ = _adapter(
        lambda c, k: [_frag(f"s{j}") for j in range(20)][:k], total_chunks=40
    )
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    # sin chunk_index, cada ventana toma los primeros 2 y se deduplican
    assert ctx.texto.split("|") == ["s0", "s1"]


def test_el_cupo_se_acota_por_presupuesto_de_contexto(monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    monkeypatch.setattr(settings, "RETRIEVAL_VENTANA_CANDIDATOS", 8)
    monkeypatch.setattr(settings, "RETRIEVAL_FRAGMENTOS_POR_VENTANA", 1)
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_CONTEXT_TOKENS", 6000)
    # 40 chunks de ~4000 caracteres (~1000 tokens): caben unos 5 en el presupuesto.
    texto_largo = "x" * 4000
    adapter, _ = _adapter(
        lambda c, k: [_frag(f"c{j}", j, texto_largo) for j in range(40)][:k],
        total_chunks=40,
    )
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))
    elegidos = ctx.texto.split("|")
    # Sin acotar saldrian 4 por ventana (40 en total). Con presupuesto, mucho menos.
    assert len(elegidos) < 40
    assert len(elegidos) <= 10


def _adapter_chunks_desiguales():
    """40 chunks en 10 ventanas: los de la primera zona son chicos y el resto, de 1.000 caracteres."""
    estado = {"ventana": -1}

    def respuestas(consulta, top_k):
        estado["ventana"] += 1
        lo = estado["ventana"] * 4
        return [
            _frag(f"c{j}", j, "x" * (200 if j < 4 else 1000))
            for j in range(lo, lo + 4)
        ][:top_k]

    return _adapter(respuestas, total_chunks=40)


def _configurar_presupuesto(monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_VENTANAS", 10)
    monkeypatch.setattr(settings, "RETRIEVAL_VENTANA_CANDIDATOS", 8)
    monkeypatch.setattr(settings, "RETRIEVAL_FRAGMENTOS_POR_VENTANA", 1)
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_CONTEXT_TOKENS", 6000)


def test_el_presupuesto_de_contexto_es_global_y_cubre_la_ultima_zona(monkeypatch):
    """NM-33 (review de Leandro): ventanas posteriores con chunks mas grandes que la primera."""
    from app.services.retrieval_service import contar_tokens_aproximado, ensamblar_contexto

    _configurar_presupuesto(monkeypatch)
    documento = _documento_largo()
    consultas = construir_consultas("titulo", documento)
    assert len(consultas) == 10  # si cambia el calculo de ventanas, ajustar el escenario

    adapter, _ = _adapter_chunks_desiguales()
    elegidos = adapter._recuperar_por_ventanas(consultas, "doc")

    # 1. Todo lo elegido cabe en el contexto real, sin superar el limite.
    texto = ensamblar_contexto(elegidos)
    assert contar_tokens_aproximado(texto) <= settings.RETRIEVAL_MAX_CONTEXT_TOKENS
    assert all(f"chunk={f.chunk_id}" in texto for f in elegidos)

    # 2. Hubo que recortar (el escenario realmente excede el presupuesto): 40 chunks no caben.
    assert len(elegidos) < 40

    # 3. Cobertura: la ultima zona ([36, 40)) y la primera aportan al menos un fragmento.
    indices = [f.metadatos["chunk_index"] for f in elegidos]
    assert any(i >= 36 for i in indices)
    assert any(i < 4 for i in indices)


def test_fuentes_coincide_con_lo_que_entra_al_contexto(monkeypatch):
    from app.services.retrieval_service import ensamblar_contexto

    _configurar_presupuesto(monkeypatch)
    adapter, _ = _adapter_chunks_desiguales()
    adapter._ensamblar = ensamblar_contexto  # el real: corta por presupuesto
    # Con el real, un fragmento queda en el contexto si su cabecera aparece en el texto.
    ctx = adapter.obtener_contexto(_payload(_documento_largo()))

    ids_fuentes = [f.chunk_id for f in ctx.fuentes]
    assert ids_fuentes
    assert all(f"chunk={cid}]" in ctx.texto or f"chunk={cid} " in ctx.texto for cid in ids_fuentes)
    assert ctx.texto.count("[Fuente:") == len(ids_fuentes)