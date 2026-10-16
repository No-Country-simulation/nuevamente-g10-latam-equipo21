"""
Contrato de desacople entre el servicio de recuperación (NM-06, ver retrieval_service.py) y el
almacén vectorial concreto (ChromaDB, implementado por NM-05).

`retrieval_service` depende exclusivamente del Protocol `VectorStore` definido acá, nunca de
ChromaDB ni de un modelo de embeddings específico. Esto permite testear la recuperación con un
store fake en memoria y reemplazar la implementación real sin modificar el servicio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


class VectorStoreError(Exception):
    """Fallo genérico al consultar el almacén vectorial."""


class VectorStoreNoDisponibleError(VectorStoreError):
    """El almacén vectorial no está inicializado, no existe o no responde."""


@dataclass(frozen=True)
class FragmentoRecuperado:
    """
    Fragmento (chunk) devuelto por el almacén vectorial junto con su trazabilidad de origen.

    `metadatos` transporta la información necesaria para citar la fuente (por ejemplo página,
    sección o título del documento original).
    """

    chunk_id: str
    documento_id: str
    texto: str
    score: float
    metadatos: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Contrato mínimo que debe cumplir el almacén vectorial usado por NM-06."""

    def buscar_similares(
        self,
        *,
        texto_consulta: str,
        top_k: int,
        documento_id: str | None = None,
    ) -> list[FragmentoRecuperado]:
        """
        Devuelve hasta `top_k` fragmentos ordenados por similitud descendente.

        `score` es una similitud normalizada en el rango 0-1 donde mayor significa más
        relevante; es responsabilidad de la implementación concreta traducir la distancia del
        motor (por ejemplo Chroma) a este score. Si `documento_id` se provee, la búsqueda se
        restringe a ese documento.

        La implementación resuelve internamente el embedding de `texto_consulta` y debe
        levantar `VectorStoreNoDisponibleError` si el almacén no está disponible, sin propagar
        la excepción específica del SDK subyacente.
        """
        ...
