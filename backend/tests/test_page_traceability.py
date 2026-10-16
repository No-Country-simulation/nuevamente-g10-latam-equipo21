"""
NM-23: trazabilidad de página de los fragmentos recuperados.

Verifica, de punta a punta del servicio de contexto, que un documento de varias páginas
conserva la página real de origen de cada fragmento recuperado (ChromaDB real en `tmp_path`
+ embeddings fake deterministas).
"""

from types import SimpleNamespace

from app.services.adaptacion_adapters import ContextoRealAdapter
from app.services.chroma_store import ChromaStore
from app.services.chroma_vector_store import ChromaVectorStore
from app.services.chunking import chunk_pages
from app.services.retrieval_service import ensamblar_contexto, recuperar_contexto


class FakeEmbeddingService:
    """Embeddings deterministas: cada dimensión cuenta ocurrencias de una palabra clave."""

    def _vector(self, texto: str) -> list[float]:
        minuscula = texto.lower()
        return [
            float(minuscula.count("python")),
            float(minuscula.count("java")),
            float(minuscula.count("datos")),
            1.0,
        ]

    def embed_documents(self, texts):
        return [self._vector(texto) for texto in texts]

    def embed_query(self, text):
        return self._vector(text)


def _payload(paginas):
    return SimpleNamespace(
        documento_titulo="Curso de Python",
        documento_contenido="\n\n".join(texto for _, texto in paginas),
        documento_paginas=[
            SimpleNamespace(page_number=numero, text=texto) for numero, texto in paginas
        ],
    )


def _adapter(tmp_path) -> ContextoRealAdapter:
    store = ChromaStore(
        embedding_service=FakeEmbeddingService(),
        persist_directory=str(tmp_path),
    )
    return ContextoRealAdapter(
        chroma_store=store,
        vector_store=ChromaVectorStore(store),
        chunker=chunk_pages,
        recuperar=recuperar_contexto,
        ensamblar=ensamblar_contexto,
    )


def test_pagina_de_origen_se_preserva_en_documento_multipagina(tmp_path):
    adapter = _adapter(tmp_path)
    payload = _payload(
        [
            (1, "Introduccion general del curso."),
            (2, "Modulo de python: variables y tipos."),
            (3, "Modulo de java: clases y objetos."),
        ]
    )

    contexto = adapter.obtener_contexto(payload)

    assert contexto.fuentes, "debe recuperar al menos un fragmento"
    assert all(fuente.pagina is not None for fuente in contexto.fuentes)
    # El fragmento más relevante para la consulta (python) sale de la página 2.
    assert contexto.fuentes[0].pagina == 2


def test_sin_paginas_el_fallback_sigue_siendo_pagina_1(tmp_path):
    """Sin `documento_paginas`, se conserva el comportamiento previo (todo en página 1)."""
    adapter = _adapter(tmp_path)
    payload = SimpleNamespace(
        documento_titulo="Curso de Python",
        documento_contenido="Modulo de python: variables y tipos.",
    )

    contexto = adapter.obtener_contexto(payload)

    assert contexto.fuentes
    assert {fuente.pagina for fuente in contexto.fuentes} == {1}
