"""Adaptadores finos entre el orquestador (NM-12) y los servicios reales.

Cableados contra código real:
- ContextoRealAdapter  -> NM-05 (chunk_pages, ChromaStore) + NM-06 (recuperar_contexto,
  ensamblar_contexto, ChromaVectorStore), ya en develop.
- GeneradorRealAdapter -> NM-08 (generar_contenido_adaptado, GeminiProvider) y
- VerificadorRealAdapter -> NM-09 (evaluar_fidelidad), con import perezoso:
  así el modo mock no carga el SDK de Gemini.

- MetadatosRealAdapter     -> NM-10 (generar_metadatos_aprendizaje).
- StorageOCIAdapter        -> NM-11 (OCIStorageService.persist_generated_package).

Persistencia (criterio de NM-12): ninguna falla de OCI invalida la respuesta; el
endpoint responde 200 con almacenamiento_oci.status_upload="error". Sobre objeto_id:
- nombre del objeto + "error": se intentó subir y la subida falló (NM-11).
- "no-persistido" + "error": ni siquiera se llegó a intentar (configuración OCI
  incompleta, credenciales inválidas, cliente que no se pudo construir).
Quien consuma la respuesta debe decidir por status_upload, nunca por objeto_id.
"""

import hashlib
import math
import logging
from functools import lru_cache

from app.core.config import settings
from app.core.errors import PipelineNoConfiguradaError
from app.schemas.output import (
    AlmacenamientoOCISchema,
    ContenidoAdaptadoSchema,
    EvaluacionCalidadSchema,
    MetadatosSchema,
    OutputSchema,
)
from app.services.adaptacion_service import (
    OBJETO_NO_PERSISTIDO,
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


def _paginas_para_indexar(payload) -> list[dict]:
    """Páginas reales del origen si el payload las trae; si no, todo el texto como página 1.

    Preservar las páginas permite que cada chunk conserve su página de origen (NM-23).
    """
    paginas = getattr(payload, "documento_paginas", None)
    if paginas:
        return [{"page_number": pagina.page_number, "text": pagina.text} for pagina in paginas]
    return [{"page_number": 1, "text": payload.documento_contenido}]


def calcular_num_ventanas(longitud: int) -> int:
    """Cantidad de secciones sobre las que se consulta el documento (NM-22).

    Hasta RETRIEVAL_VENTANA_CHARS se usa una sola consulta (comportamiento original):
    un documento así tiene pocos chunks y el top_k ya lo cubre. Más allá, una ventana
    por cada RETRIEVAL_VENTANA_CHARS, con tope en RETRIEVAL_MAX_VENTANAS.
    """
    if longitud <= settings.RETRIEVAL_VENTANA_CHARS:
        return 1
    tope = max(1, settings.RETRIEVAL_MAX_VENTANAS)
    return min(tope, math.ceil(longitud / settings.RETRIEVAL_VENTANA_CHARS))


def dividir_en_ventanas(contenido: str, cantidad: int) -> list[str]:
    """Divide el contenido en `cantidad` secciones contiguas de largo similar."""
    if cantidad <= 1:
        return [contenido]
    tamano = math.ceil(len(contenido) / cantidad)
    ventanas = [contenido[i * tamano:(i + 1) * tamano] for i in range(cantidad)]
    return [v for v in ventanas if v.strip()]


def construir_consultas(titulo: str, contenido: str) -> list[str]:
    """Una consulta por sección: título + primeros CONSULTA_MAX_CHARS de cada una."""
    cantidad = calcular_num_ventanas(len(contenido))
    if cantidad == 1:
        return [construir_consulta(titulo, contenido)]
    return [construir_consulta(titulo, v) for v in dividir_en_ventanas(contenido, cantidad)]


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

    def _recuperar_por_ventanas(self, consultas: list[str], doc_id: str) -> list:
        """Recupera por sección y une sin duplicados, en orden de documento (NM-22).

        El top_k global se reparte entre las secciones (mínimo 1 por sección), de modo
        que el total de fragmentos queda en max(RETRIEVAL_TOP_K, secciones) y entra en
        RETRIEVAL_MAX_CONTEXT_TOKENS sin que ensamblar_contexto corte los últimos.
        """
        por_ventana = max(1, settings.RETRIEVAL_TOP_K // len(consultas))
        vistos: set[str] = set()
        unidos = []
        for consulta in consultas:
            for fragmento in self._recuperar(
                consulta=consulta,
                vector_store=self._vector_store,
                documento_id=doc_id,
                top_k=por_ventana,
            ):
                if fragmento.chunk_id in vistos:
                    continue
                vistos.add(fragmento.chunk_id)
                unidos.append(fragmento)
        return unidos

    def obtener_contexto(self, payload) -> ContextoRecuperado:
        self._init_real()
        doc_id = documento_id_desde_contenido(payload.documento_contenido)

        # Indexa solo si el documento aún no está (evita re-embeber: cuota de Gemini).
        if self._store.count_document(doc_id) == 0:
            chunks = self._chunker(
                document_id=doc_id,
                pages=_paginas_para_indexar(payload),
            )
            self._store.index_chunks(chunks)

        consultas = construir_consultas(payload.documento_titulo, payload.documento_contenido)
        if len(consultas) == 1:
            fragmentos = self._recuperar(
                consulta=consultas[0],
                vector_store=self._vector_store,
                documento_id=doc_id,
            )
        else:
            fragmentos = self._recuperar_por_ventanas(consultas, doc_id)
        texto = self._ensamblar(fragmentos) if fragmentos else ""
        fuentes = [
            FuenteContexto(
                chunk_id=f.chunk_id,
                pagina=(f.metadatos or {}).get("pagina"),
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
    """NM-08. Import perezoso: evita cargar el SDK de Gemini en modo mock."""

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
    del adaptador de contexto. Import perezoso: evita cargar el SDK de Gemini en modo mock."""

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
        
class MetadatosRealAdapter:
    """NM-10. Conceptos clave, prerrequisitos y tiempo estimado de estudio."""

    def __init__(self, llm_provider=None, generar=None) -> None:
        self._llm = llm_provider
        self._generar = generar

    def generar(self, payload, contenido):
        if self._generar is None:
            from app.services.metadata_service import generar_metadatos_aprendizaje
            self._generar = generar_metadatos_aprendizaje
        if self._llm is None:
            self._llm = _llm_provider_compartido()
        return self._generar(
            documento_contenido=payload.documento_contenido,
            contenido_adaptado=contenido,
            perfil_destinatario=payload.perfil_destinatario,
            formato_salida=payload.formato_salida,
            llm_provider=self._llm,
        )


def armar_respuesta_provisional(paquete: dict) -> OutputSchema:
    """Reconstruye el OutputSchema que exige OCIStorageService.persist_generated_package.

    El puerto Storage entrega el paquete como dict; NM-11 pide un OutputSchema. El
    bloque almacenamiento_oci es provisional (status_upload="error"): NM-11 lo
    reemplaza con el resultado real de la subida.
    """
    return OutputSchema(
        status="exito",
        metadatos=MetadatosSchema.model_validate(paquete["metadatos"]),
        contenido_adaptado=ContenidoAdaptadoSchema.model_validate(paquete["contenido_adaptado"]),
        evaluacion_calidad=EvaluacionCalidadSchema.model_validate(paquete["evaluacion_calidad"]),
        almacenamiento_oci=AlmacenamientoOCISchema(
            bucket=settings.OCI_BUCKET_NAME,
            objeto_id=OBJETO_NO_PERSISTIDO,
            status_upload="error",
        ),
    )


class StorageOCIAdapter:
    """NM-11. Persiste el paquete generado en OCI Object Storage.

    El servicio OCI se construye de forma perezosa en el primer guardar(), no al
    instanciar el adaptador: _servicio_real() está cacheado y construir el cliente
    ahí fijaría para siempre un fallo de configuración. Solo se conserva el servicio
    si se pudo construir; si la fábrica lanza, la excepción sube a
    AdaptacionService._persistir, que la convierte en status_upload="error".
    """

    def __init__(self, service_factory=None) -> None:
        self._factory = service_factory
        self._servicio = None

    def _obtener_servicio(self):
        if self._servicio is None:
            factory = self._factory
            if factory is None:
                from app.services.oci_storage_service import get_oci_storage_service
                factory = get_oci_storage_service
            self._servicio = factory()
        return self._servicio

    def guardar(self, payload, paquete) -> AlmacenamientoOCISchema:
        servicio = self._obtener_servicio()
        persistido = servicio.persist_generated_package(
            payload=payload,
            response=armar_respuesta_provisional(paquete),
        )
        return persistido.almacenamiento_oci


@lru_cache(maxsize=1)
def _servicio_real() -> AdaptacionService:
    contexto = ContextoRealAdapter()
    return AdaptacionService(
        contexto=contexto,
        generador=GeneradorRealAdapter(),
        verificador=VerificadorRealAdapter(contexto),
        metadatos=MetadatosRealAdapter(),
        storage=StorageOCIAdapter(),
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
