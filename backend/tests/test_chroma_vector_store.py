"""
Pruebas de la búsqueda semántica sobre ChromaStore real (NM-06).

Se usa ChromaDB real persistido en `tmp_path` (igual que NM-05) junto con un servicio de
embeddings fake, de modo que los tests no dependen de Gemini ni de red. Los vectores del fake
son deterministas para poder afirmar el orden de relevancia.
"""

from app.services.chroma_store import ChromaStore
from app.services.chunking import TextChunk
from app.services.chroma_vector_store import ChromaVectorStore
from app.services.retrieval_service import ensamblar_contexto, recuperar_contexto
from app.services.vector_store import VectorStore


class FakeEmbeddingService:
    """
    Servicio de embeddings determinista: cada dimensión cuenta ocurrencias de una palabra clave.

    Así una consulta "python" queda idéntica al chunk que habla de python (distancia 0) y más
    lejos de los chunks que hablan de otro tema.
    """

    _PALABRAS = ("python", "java", "datos")

    def _vector(self, texto: str) -> list[float]:
        minuscula = texto.lower()
        return [float(minuscula.count(palabra)) for palabra in self._PALABRAS] + [1.0]

    def embed_documents(self, texts):
        return [self._vector(texto) for texto in texts]

    def embed_query(self, text):
        return self._vector(text)


def _chunk(document_id, chunk_index, text, page_number=1):
    return TextChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        text=text,
        page_number=page_number,
        char_start=0,
        char_end=len(text),
    )


def _store_con(chunks, tmp_path):
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )
    # `index_chunks` exige chunks de un único documento por llamada.
    por_documento: dict[str, list[TextChunk]] = {}
    for chunk in chunks:
        por_documento.setdefault(chunk.document_id, []).append(chunk)
    for grupo in por_documento.values():
        store.index_chunks(grupo)
    return store


def test_buscar_devuelve_el_mas_similar_primero(tmp_path):
    """El fragmento más cercano a la consulta encabeza los resultados, con su trazabilidad."""
    store = _store_con(
        [
            _chunk("doc-001", 0, "curso de python avanzado", 1),
            _chunk("doc-001", 1, "curso de java basico", 2),
        ],
        tmp_path,
    )
    vector_store = ChromaVectorStore(store)

    resultados = vector_store.buscar_similares(texto_consulta="python", top_k=5)

    assert resultados[0].chunk_id == "doc-001:0"
    assert resultados[0].documento_id == "doc-001"
    assert resultados[0].texto == "curso de python avanzado"
    assert resultados[0].metadatos["pagina"] == 1


def test_score_en_rango_y_orden_descendente(tmp_path):
    """Los scores quedan en [0, 1] y vienen ordenados de mayor a menor similitud."""
    store = _store_con(
        [
            _chunk("doc-001", 0, "python"),
            _chunk("doc-001", 1, "python y datos"),
            _chunk("doc-001", 2, "java sin relacion"),
        ],
        tmp_path,
    )
    vector_store = ChromaVectorStore(store)

    resultados = vector_store.buscar_similares(texto_consulta="python", top_k=5)

    scores = [fragmento.score for fragmento in resultados]
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert scores == sorted(scores, reverse=True)


def test_restringe_busqueda_a_un_documento(tmp_path):
    """Con `documento_id`, solo se devuelven fragmentos de ese documento."""
    store = _store_con(
        [
            _chunk("doc-001", 0, "python uno", 1),
            _chunk("doc-002", 0, "python dos", 1),
        ],
        tmp_path,
    )
    vector_store = ChromaVectorStore(store)

    resultados = vector_store.buscar_similares(
        texto_consulta="python", top_k=5, documento_id="doc-002"
    )

    assert [fragmento.documento_id for fragmento in resultados] == ["doc-002"]
    assert [fragmento.chunk_id for fragmento in resultados] == ["doc-002:0"]


def test_respeta_top_k(tmp_path):
    """No se devuelven más fragmentos que `top_k`."""
    store = _store_con(
        [
            _chunk("doc-001", 0, "python uno"),
            _chunk("doc-001", 1, "python dos"),
            _chunk("doc-001", 2, "python tres"),
        ],
        tmp_path,
    )
    vector_store = ChromaVectorStore(store)

    resultados = vector_store.buscar_similares(texto_consulta="python", top_k=1)

    assert len(resultados) == 1


def test_coleccion_vacia_devuelve_vacio(tmp_path):
    """Sin chunks indexados, la búsqueda devuelve una lista vacía."""
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )
    vector_store = ChromaVectorStore(store)

    assert vector_store.buscar_similares(texto_consulta="python", top_k=5) == []


def test_top_k_no_positivo_devuelve_vacio(tmp_path):
    """Un `top_k` <= 0 no consulta el almacén y devuelve vacío."""
    store = _store_con([_chunk("doc-001", 0, "python")], tmp_path)
    vector_store = ChromaVectorStore(store)

    assert vector_store.buscar_similares(texto_consulta="python", top_k=0) == []


def test_es_conforme_al_protocolo_vector_store(tmp_path):
    """`ChromaVectorStore` cumple el contrato `VectorStore` que consume `retrieval_service`."""
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )

    assert isinstance(ChromaVectorStore(store), VectorStore)


def test_integracion_con_recuperacion_y_ensamblado(tmp_path):
    """La búsqueda real se integra con `recuperar_contexto` y `ensamblar_contexto` de punta a punta."""
    store = _store_con(
        [
            _chunk("doc-001", 0, "guia de python para datos", 1),
            _chunk("doc-001", 1, "introduccion a java", 2),
        ],
        tmp_path,
    )
    vector_store = ChromaVectorStore(store)

    coincidencias = recuperar_contexto(
        consulta="python",
        vector_store=vector_store,
        top_k=5,
        umbral=0.0,
    )
    contexto = ensamblar_contexto(coincidencias)

    assert coincidencias[0].chunk_id == "doc-001:0"
    assert "guia de python para datos" in contexto
    assert "documento=doc-001" in contexto
    assert "pagina=1" in contexto
