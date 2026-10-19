"""
Servicio de recuperación de contexto por similitud semántica (NM-06).

Dada una consulta, obtiene los fragmentos más relevantes del `VectorStore` (ver
vector_store.py), descarta los que no superan el umbral de similitud y ensambla un contexto de
texto plano acotado por un límite máximo de tokens, listo para anclarse al prompt de generación
(`orchestration_service.generar_contenido_adaptado`, NM-08).

Este módulo depende exclusivamente del Protocol `VectorStore`, nunca de ChromaDB ni de un modelo
de embeddings concreto: eso permite testear la recuperación con un store fake y reemplazar la
implementación real (NM-05) sin tocar esta capa.
"""

from __future__ import annotations

import math
from typing import Callable

from app.core.config import settings
from app.services.vector_store import FragmentoRecuperado, VectorStore


def contar_tokens_aproximado(texto: str) -> int:
    """
    Estimación de tokens sin dependencias externas (aprox. 4 caracteres por token).

    Es una aproximación deliberada para el MVP: alcanza para acotar el contexto sin atar el
    servicio a un tokenizer concreto. Puede reemplazarse por `tiktoken` u otro contador
    inyectando el callable correspondiente en `ensamblar_contexto`.
    """
    return math.ceil(len(texto) / 4)


def recuperar_contexto(
    *,
    consulta: str,
    vector_store: VectorStore,
    top_k: int | None = None,
    umbral: float | None = None,
    documento_id: str | None = None,
) -> list[FragmentoRecuperado]:
    """
    Devuelve los fragmentos relevantes para `consulta`, filtrados por `umbral`.

    Respeta `top_k` (por defecto `settings.RETRIEVAL_TOP_K`) y restringe la búsqueda a
    `documento_id` si se provee. Los resultados se devuelven ordenados por score descendente.
    Si ningún fragmento alcanza `umbral` (por defecto `settings.RETRIEVAL_SCORE_THRESHOLD`), la
    lista es vacía: nunca se devuelven fragmentos irrelevantes.

    No reordena ni re-puntúa los resultados: el reranking queda fuera de alcance de NM-06.
    """
    limite = settings.RETRIEVAL_TOP_K if top_k is None else top_k
    minimo = settings.RETRIEVAL_SCORE_THRESHOLD if umbral is None else umbral

    coincidencias = vector_store.buscar_similares(
        texto_consulta=consulta,
        top_k=limite,
        documento_id=documento_id,
    )

    relevantes = [coincidencia for coincidencia in coincidencias if coincidencia.score >= minimo]
    relevantes.sort(key=lambda coincidencia: coincidencia.score, reverse=True)
    return relevantes


def _referencia(fragmento: FragmentoRecuperado) -> str:
    """
    Construye la línea de trazabilidad del fragmento para poder citar la fuente.

    Expone el documento y el chunk, más los metadatos de origen conocidos (página, sección,
    título) cuando estén presentes.
    """
    partes = [f"documento={fragmento.documento_id}", f"chunk={fragmento.chunk_id}"]
    for clave in ("pagina", "seccion", "titulo"):
        if clave in fragmento.metadatos:
            partes.append(f"{clave}={fragmento.metadatos[clave]}")
    return "[Fuente: " + " | ".join(partes) + "]"


def ensamblar_contexto(
    coincidencias: list[FragmentoRecuperado],
    *,
    max_tokens: int | None = None,
    contar_tokens: Callable[[str], int] = contar_tokens_aproximado,
) -> str:
    """
    Ensambla `coincidencias` en un único texto de contexto, acotado por `max_tokens`.

    Recorre los fragmentos en el orden recibido (de mayor a menor relevancia, tal como los
    devuelve `recuperar_contexto`) y agrega cada uno precedido por su referencia de origen
    mientras el total acumulado no supere `max_tokens` (por defecto
    `settings.RETRIEVAL_MAX_CONTEXT_TOKENS`). Al encontrar un fragmento que no entra, detiene el
    armado: como vienen ordenados por relevancia, lo que queda afuera es lo menos relevante.

    Devuelve cadena vacía si no hay coincidencias.
    """
    limite = settings.RETRIEVAL_MAX_CONTEXT_TOKENS if max_tokens is None else max_tokens

    bloques: list[str] = []
    for fragmento in coincidencias:
        bloque = f"{_referencia(fragmento)}\n{fragmento.texto}"
        candidato = "\n\n".join([*bloques, bloque])
        if contar_tokens(candidato) > limite:
            break
        bloques.append(bloque)

    return "\n\n".join(bloques)
