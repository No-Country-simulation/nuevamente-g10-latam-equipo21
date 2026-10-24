"""Identidad estable para documentos procesados por la API."""

import hashlib


def documento_id_desde_contenido(contenido: str) -> str:
    """El mismo texto extraído produce siempre el mismo identificador."""
    return "doc-" + hashlib.sha256(contenido.encode("utf-8")).hexdigest()[:16]
