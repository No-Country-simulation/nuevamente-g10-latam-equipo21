
from typing import List

from google import genai
from google.genai import types

from app.core.config import settings


class EmbeddingServiceError(Exception):
    """Error al generar embeddings para el pipeline RAG."""


class GeminiEmbeddingService:
    """
    Servicio encargado de convertir textos en vectores numéricos
    utilizando el modelo de embeddings de Google Gemini.

    Los embeddings generados se usan para indexar documentos
    en ChromaDB y permitir búsquedas semánticas.

    Los documentos se procesan en lotes de hasta 100 textos,
    respetando el límite de Gemini.
    """

    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client=None,
    ):
        self.model_name = (
            model_name
            or settings.GEMINI_EMBEDDING_MODEL_NAME
        )

        # Permite utilizar un cliente falso en los tests.
        if client is not None:
            self.client = client
            return

        # Si api_key es None, utiliza la configuración.
        # Una cadena vacía explícita se considera inválida.
        key = (
            settings.GEMINI_API_KEY
            if api_key is None
            else api_key
        )

        if not key:
            raise EmbeddingServiceError(
                "No se configuró GEMINI_API_KEY."
            )

        self.client = genai.Client(api_key=key)

    def embed_documents(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Genera embeddings para documentos utilizando
        RETRIEVAL_DOCUMENT.
        """

        return self._embed(
            texts,
            task_type="RETRIEVAL_DOCUMENT",
        )

    def embed_query(
        self,
        text: str,
    ) -> List[float]:
        """
        Genera el embedding de una consulta utilizando
        RETRIEVAL_QUERY.
        """

        return self._embed(
            [text],
            task_type="RETRIEVAL_QUERY",
        )[0]

    def _embed(
        self,
        texts: List[str],
        task_type: str,
    ) -> List[List[float]]:
        """
        Genera embeddings en lotes de hasta 100 textos.

        Garantiza:
        - Cantidad de embeddings igual a la de textos.
        - Conservación del orden original.
        - Ningún resultado parcial ante errores.
        """

        if not texts:
            return []

        if any(not isinstance(text, str) for text in texts):
            raise ValueError(
                "Todos los documentos deben ser strings."
            )

        if any(not text.strip() for text in texts):
            raise ValueError(
                "No se pueden generar embeddings de textos vacíos."
            )

        embeddings: List[List[float]] = []

        for start in range(
            0,
            len(texts),
            self.MAX_BATCH_SIZE,
        ):
            batch = texts[
                start:start + self.MAX_BATCH_SIZE
            ]

            batch_number = (
                start // self.MAX_BATCH_SIZE
            ) + 1

            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                    ),
                )

                if not response.embeddings:
                    raise EmbeddingServiceError(
                        f"Gemini no devolvió embeddings "
                        f"para el lote {batch_number}."
                    )

                if len(response.embeddings) != len(batch):
                    raise EmbeddingServiceError(
                        f"Cantidad incorrecta de embeddings "
                        f"en el lote {batch_number}: "
                        f"esperados {len(batch)}, "
                        f"recibidos {len(response.embeddings)}."
                    )

                batch_embeddings = []

                for embedding in response.embeddings:
                    if (
                        embedding.values is None
                        or len(embedding.values) == 0
                    ):
                        raise EmbeddingServiceError(
                            f"Gemini devolvió un vector vacío "
                            f"en el lote {batch_number}."
                        )

                    batch_embeddings.append(
                        list(embedding.values)
                    )

                embeddings.extend(batch_embeddings)

            except EmbeddingServiceError:
                raise

            except Exception as exc:
                raise EmbeddingServiceError(
                    f"Error generando embeddings "
                    f"en el lote {batch_number}: {exc}"
                ) from exc

        return embeddings
