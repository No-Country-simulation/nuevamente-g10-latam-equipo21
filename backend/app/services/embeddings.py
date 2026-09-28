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

    Los embeddings generados se usarán para indexar documentos
    en ChromaDB y posteriormente permitir búsqueda semántica.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client=None,
    ):
        # Modelo de embeddings configurado en settings.
        self.model_name = (
            model_name
            or settings.GEMINI_EMBEDDING_MODEL_NAME
        )

        # Permite utilizar un cliente falso en los tests
        # sin realizar llamadas reales a Gemini.
        if client is not None:
            self.client = client
            return

        # Si api_key es None, toma la clave del archivo .env.
        # Si se pasa explícitamente "", debe considerarse inválida.
        key = (
            settings.GEMINI_API_KEY
            if api_key is None
            else api_key
        )

        if not key:
            raise EmbeddingServiceError(
                "No se configuró GEMINI_API_KEY."
            )

        self.client = genai.Client(
            api_key=key
        )

    def embed_documents(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Genera embeddings para una lista de textos.

        Se utiliza RETRIEVAL_DOCUMENT porque estos textos
        serán almacenados en ChromaDB para recuperación
        semántica posterior.
        """

        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(
        self,
        text: str,
    ) -> List[float]:
        """
        Genera el embedding de una consulta de búsqueda.

        Se utiliza RETRIEVAL_QUERY (distinto de RETRIEVAL_DOCUMENT) porque Gemini recomienda
        un task type específico para el lado consulta; mejora la calidad de la recuperación
        frente a reutilizar el embedding de documento.
        """

        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]

    def _embed(
        self,
        texts: List[str],
        task_type: str,
    ) -> List[List[float]]:
        """
        Lógica común de generación de embeddings para un `task_type` dado.
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

        try:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type
                ),
            )

            if not response.embeddings:
                raise EmbeddingServiceError(
                    "Gemini no devolvió embeddings."
                )

            return [
                list(embedding.values)
                for embedding in response.embeddings
            ]

        except EmbeddingServiceError:
            raise

        except Exception as exc:
            raise EmbeddingServiceError(
                f"Error generando embeddings: {exc}"
            ) from exc