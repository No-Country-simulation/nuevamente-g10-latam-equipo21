"""Adaptadores finos entre el orquestador (NM-12) y los servicios reales.

Cableados contra código real:
- ContextoRealAdapter  -> NM-05 (chunk_pages, ChromaStore) + NM-06 (recuperar_contexto,
  ensamblar_contexto, ChromaVectorStore), ya en develop.
- GeneradorRealAdapter -> NM-08 (generar_contenido_adaptado, GeminiProvider) y
- VerificadorRealAdapter -> NM-09 (evaluar_fidelidad), que viven aún en sus ramas:
  se importan de forma perezosa para no romper develop.

PENDIENTES (levantan PipelineNoConfiguradaError -> HTTP 501):
- MetadatosRealAdapter (NM-10).
- StorageNoDisponible (NM-11): la subida "falla" y el endpoint responde 200 con
  almacenamiento_oci.status_upload="error", como exige NM-12.
"""

import hashlib
import logging
from functools import lru_cache

from app.core.errors import PipelineNoConfiguradaError
from app.services.adaptacion_service import (
    AdaptacionService,
    ContextoRecuperado,
    FuenteContexto,
)

logger = logging.getLogger("nuevamente.adaptacion")

CONSULTA_MAX_CHARS = 500


def documento_id_desde_contenido(contenido: str) -> str:
    """El contrato no trae documento_id: se deriva del contenido (mismo texto -> mismo id)."""
    return "doc-" + hashlib.sha256(contenido.encode("utf-8")).hexdigest()[:16]


def construir_consulta(titulo: str, contenido: str) -> str:
    return f"{titulo}\n{contenido[:CONSULTA_MAX_CHARS]}"


class ContextoRealAdapter:
    """NM-05 (indexar) + NM-06 (recuperar). Todo inyectable para tests."""

    def __init__(self, chroma_store=None, vector_store=None,
                 chunker=None, recuperar=None, ensamblar=None) -> None:
        self._store = chroma_store
        self._vector_store = vector_store
        self._chunker = chunker
        self._recuperar = recuperar
        self._ensamblar = ensamblar

    def _init_real(self) -> None:
        if self._store is not None:
            return
        from app.services.chroma_store import ChromaStore
        from app.services.chroma_vector_store import ChromaVectorStore
        from app.services.chunking import chunk_pages
        from app.services.embeddings import GeminiEmbeddingService
        from app.services.retrieval_service import ensamblar_contexto, recuperar_contexto

        self._store = ChromaStore(embedding_service=GeminiEmbeddingService())
        self._vector_store = ChromaVectorStore(self._store)
        self._chunker = chunk_pages
        self._recuperar = recuperar_contexto
        self._ensamblar = ensamblar_contexto

    @property
    def vector_store(self):
        """Lo reutiliza el verificador de NM-09 (hace su propio retrieval)."""
        self._init_real()
        return self._vector_store

    def obtener_contexto(self, payload) -> ContextoRecuperado:
        self._init_real()
        doc_id = documento_id_desde_contenido(payload.documento_contenido)

        # Indexa solo si el documento aún no está (evita re-embeber: cuota de Gemini).
        if self._store.count_document(doc_id) == 0:
            chunks = self._chunker(
                document_id=doc_id,
                pages=[{"page_number": 1, "text": payload.documento_contenido}],
            )
            self._store.index_chunks(chunks)

        fragmentos = self._recuperar(
            consulta=construir_consulta(payload.documento_titulo, payload.documento_contenido),
            vector_store=self._vector_store,
            documento_id=doc_id,
        )
        texto = self._ensamblar(fragmentos) if fragmentos else ""
        fuentes = [
            FuenteContexto(
                chunk_id=f.chunk_id,
                pagina=(f.metadatos or {}).get("page_number"),
                score=f.score,
            )
            for f in fragmentos
        ]
        return ContextoRecuperado(texto=texto, fuentes=fuentes)


@lru_cache(maxsize=1)
def _llm_provider_compartido():
    """Un solo GeminiProvider para generación (NM-08) y verificación (NM-09)."""
    from app.services.gemini_provider import GeminiProvider
    return GeminiProvider.desde_configuracion()


class GeneradorRealAdapter:
    """NM-08. Import perezoso: el módulo aún no está en develop."""

    def __init__(self, llm_provider=None, generar=None) -> None:
        self._llm = llm_provider
        self._generar = generar

    def generar(self, payload, contexto):
        if self._generar is None:
            from app.services.orchestration_service import generar_contenido_adaptado
            self._generar = generar_contenido_adaptado
        if self._llm is None:
            self._llm = _llm_provider_compartido()
        return self._generar(
            documento_titulo=payload.documento_titulo,
            contexto_recuperado=contexto.texto,
            perfil_destinatario=payload.perfil_destinatario.value,
            formato_salida=payload.formato_salida.value,
            nicho_sector=payload.nicho_sector.value,
            nivel_detalle=payload.nivel_detalle.value,
            llm_provider=self._llm,
        )


class _SinCablear:
    sin_cablear = True

    def _no(self):
        raise PipelineNoConfiguradaError()


class VerificadorRealAdapter:
    """NM-09. evaluar_fidelidad hace su propio retrieval por unidad de contenido:
    necesita el documento_id (mismo hash que usó el indexado) y el vector store
    del adaptador de contexto. Import perezoso: aún no está en develop."""

    def __init__(self, contexto_adapter, llm_provider=None, evaluar=None) -> None:
        self._contexto = contexto_adapter
        self._llm = llm_provider
        self._evaluar = evaluar

    def evaluar(self, payload, contenido, contexto):
        if self._evaluar is None:
            from app.services.fidelity_service import evaluar_fidelidad
            self._evaluar = evaluar_fidelidad
        if self._llm is None:
            self._llm = _llm_provider_compartido()
        return self._evaluar(
            documento_id=documento_id_desde_contenido(payload.documento_contenido),
            contenido_adaptado=contenido,
            vector_store=self._contexto.vector_store,
            llm_provider=self._llm,
            perfil_destinatario=payload.perfil_destinatario.value,
        )


class MetadatosRealAdapter(_SinCablear):         # NM-10 (sin tomar)
    def generar(self, payload, contenido):
        self._no()


class StorageNoDisponible:                       # NM-11 (sin tomar)
    def guardar(self, payload, paquete):
        raise RuntimeError("NM-11 no implementado: sin persistencia en OCI")


@lru_cache(maxsize=1)
def _servicio_real() -> AdaptacionService:
    contexto = ContextoRealAdapter()
    return AdaptacionService(
        contexto=contexto,
        generador=GeneradorRealAdapter(),
        verificador=VerificadorRealAdapter(contexto),
        metadatos=MetadatosRealAdapter(),
        storage=StorageNoDisponible(),
    )


def construir_servicio_real() -> AdaptacionService:
    """Falla rápido (501) si algún paso obligatorio sigue sin cablear, ANTES de
    indexar o llamar a Gemini: no se gasta cuota para terminar en error."""
    servicio = _servicio_real()
    pendientes = [
        type(c).__name__
        for c in (servicio._verificador, servicio._metadatos)
        if getattr(c, "sin_cablear", False)
    ]
    if pendientes:
        logger.warning("Pipeline real no disponible; pasos sin cablear: %s", pendientes)
        raise PipelineNoConfiguradaError()
    return servicio
