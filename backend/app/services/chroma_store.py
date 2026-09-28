from pathlib import Path
from typing import List

import chromadb

from app.core.config import settings
from app.services.chunking import TextChunk
from app.services.embeddings import GeminiEmbeddingService


class ChromaStoreError(Exception):
    """Error al operar con ChromaDB."""


class ChromaStore:
    """
    Almacén vectorial persistente para los chunks del pipeline RAG.

    - Persiste los datos en disco.
    - Genera IDs determinísticos por documento/chunk.
    - Reindexar un documento reemplaza sus chunks anteriores.
    """

    def __init__(
        self,
        embedding_service: GeminiEmbeddingService,
        persist_directory: str | None = None,
        collection_name: str = "nuevamente_documents",
    ):
        self.embedding_service = embedding_service

        self.persist_directory = (
            persist_directory
            or settings.CHROMA_PERSIST_DIRECTORY
        )

        Path(self.persist_directory).mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = chromadb.PersistentClient(
            path=self.persist_directory
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks(
        self,
        chunks: List[TextChunk],
    ) -> int:
        """
        Genera embeddings e indexa los chunks en ChromaDB.

        Si el documento ya estaba indexado, elimina primero
        sus chunks anteriores para evitar duplicados.
        """

        if not chunks:
            return 0

        document_ids = {
            chunk.document_id
            for chunk in chunks
        }

        if len(document_ids) != 1:
            raise ValueError(
                "Todos los chunks deben pertenecer al mismo documento."
            )

        document_id = chunks[0].document_id

        texts = [
            chunk.text
            for chunk in chunks
        ]

        embeddings = (
            self.embedding_service.embed_documents(texts)
        )

        if len(embeddings) != len(chunks):
            raise ChromaStoreError(
                "La cantidad de embeddings no coincide "
                "con la cantidad de chunks."
            )

        # Idempotencia:
        # eliminamos la versión anterior del documento.
        self.collection.delete(
            where={"document_id": document_id}
        )

        ids = [
            f"{chunk.document_id}:{chunk.chunk_index}"
            for chunk in chunks
        ]

        metadatas = [
            {
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
            }
            for chunk in chunks
        ]

        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(chunks)

    def count_document(
        self,
        document_id: str,
    ) -> int:
        """
        Devuelve cuántos chunks hay almacenados
        para un documento determinado.
        """

        result = self.collection.get(
            where={"document_id": document_id}
        )

        return len(result["ids"])