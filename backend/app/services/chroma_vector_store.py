"""
Implementación concreta de `VectorStore` (ver vector_store.py) sobre el `ChromaStore` real de
NM-05.

Es la única pieza de NM-06 que conoce detalles de ChromaDB: traduce la distancia coseno que
devuelve Chroma a un score de similitud 0-1 y arma los `FragmentoRecuperado` con su
trazabilidad de origen. `retrieval_service` depende solo del Protocol, nunca de esta clase.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.services.chroma_store import ChromaStore
from app.services.vector_store import (
    FragmentoRecuperado,
    VectorStoreError,
    VectorStoreNoDisponibleError,
)


class ChromaVectorStore:
    """
    Búsqueda semántica por consulta sobre un `ChromaStore` (NM-05).

    La búsqueda por consulta no forma parte de NM-05; este wrapper la implementa del lado de
    NM-06 reutilizando la colección y el servicio de embeddings ya configurados en el store.
    """

    def __init__(
        self,
        chroma_store: ChromaStore,
        embedding_service=None,
    ) -> None:
        self._store = chroma_store
        self._embeddings = embedding_service or chroma_store.embedding_service

    def buscar_similares(
        self,
        *,
        texto_consulta: str,
        top_k: int,
        documento_id: str | None = None,
    ) -> list[FragmentoRecuperado]:
        """
        Devuelve hasta `top_k` fragmentos ordenados por similitud descendente.

        Chroma ya devuelve los resultados por distancia coseno ascendente (similitud
        descendente). El `score` expuesto es `1 - distancia`, recortado a [0, 1].
        """

        if top_k <= 0:
            return []

        try:
            total = self._store.collection.count()
        except Exception as exc:
            raise VectorStoreNoDisponibleError(
                f"No se pudo acceder a la colección vectorial: {exc}"
            ) from exc

        if total == 0:
            return []

        try:
            vector_consulta = self._embeddings.embed_query(texto_consulta)
        except Exception as exc:
            raise VectorStoreError(
                f"No se pudo generar el embedding de la consulta: {exc}"
            ) from exc

        where = {"document_id": documento_id} if documento_id else None

        try:
            resultado = self._store.collection.query(
                query_embeddings=[vector_consulta],
                n_results=min(top_k, total),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreNoDisponibleError(
                f"No se pudo consultar el almacén vectorial: {exc}"
            ) from exc

        return self._mapear(resultado)

    @staticmethod
    def _mapear(resultado: Mapping[str, Any]) -> list[FragmentoRecuperado]:
        """Traduce la respuesta de Chroma a `FragmentoRecuperado` con su trazabilidad."""

        ids = (resultado.get("ids") or [[]])[0]
        documentos = (resultado.get("documents") or [[]])[0]
        metadatos = (resultado.get("metadatas") or [[]])[0]
        distancias = (resultado.get("distances") or [[]])[0]

        fragmentos: list[FragmentoRecuperado] = []
        for chunk_id, texto, metadata, distancia in zip(
            ids, documentos, metadatos, distancias
        ):
            metadata = metadata or {}
            fragmentos.append(
                FragmentoRecuperado(
                    chunk_id=chunk_id,
                    documento_id=metadata.get("document_id", ""),
                    texto=texto or "",
                    score=ChromaVectorStore._similitud(distancia),
                    metadatos={
                        "pagina": metadata.get("page_number"),
                        "chunk_index": metadata.get("chunk_index"),
                        "char_start": metadata.get("char_start"),
                        "char_end": metadata.get("char_end"),
                    },
                )
            )

        return fragmentos

    @staticmethod
    def _similitud(distancia: float) -> float:
        """Convierte una distancia coseno de Chroma en una similitud acotada a [0, 1]."""

        return max(0.0, min(1.0, 1.0 - float(distancia)))
