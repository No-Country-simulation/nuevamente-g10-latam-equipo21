"""Orquestador de la pipeline real de adaptación (NM-12).

Solo coordina: cada paso vive en su propio servicio (NM-05/06 contexto,
NM-08 generación, NM-09 fidelidad, NM-10 metadatos, NM-11 persistencia) y se
inyecta como "puerto" (Protocol). Así el endpoint no reimplementa nada ajeno y
los tests usan fakes.

Política de errores:
- Falla el contexto (vector store)  -> VectorStoreError (HTTP 502)
- Falla generación o fidelidad (LLM) -> LLMError (HTTP 502)
- Falla la subida a OCI             -> NO invalida la respuesta: 200 con
  almacenamiento_oci.status_upload = "error" (criterio de NM-12).
- Los AppError ya tipados se propagan tal cual.
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings
from app.core.errors import AppError, LLMError, SinContextoRelevanteError, VectorStoreError
from app.core.request_context import get_request_id
from app.core.log_sanitizer import error_sanitizado
from app.schemas.input import InputSchema
from app.schemas.output import (
    AlmacenamientoOCISchema,
    ContenidoAdaptadoSchema,
    EvaluacionCalidadSchema,
    MetadatosSchema,
    OutputSchema,
)

logger = logging.getLogger("nuevamente.adaptacion")

OBJETO_NO_PERSISTIDO = "no-persistido"


@dataclass(frozen=True)
class FuenteContexto:
    """Trazabilidad (Regla 9 del blueprint): chunk/página que fundamenta el contenido."""
    chunk_id: str
    pagina: int | None = None
    score: float | None = None


@dataclass(frozen=True)
class ContextoRecuperado:
    texto: str
    fuentes: list[FuenteContexto] = field(default_factory=list)


class ContextoProvider(Protocol):
    """NM-05 + NM-06: indexa documento_contenido y recupera el contexto relevante."""
    def obtener_contexto(self, payload: InputSchema) -> ContextoRecuperado: ...


class Generador(Protocol):
    """NM-08: genera el contenido adaptado por perfil/formato/nicho/nivel."""
    def generar(self, payload: InputSchema, contexto: ContextoRecuperado) -> ContenidoAdaptadoSchema: ...


class VerificadorFidelidad(Protocol):
    """NM-09: evalúa el contenido generado contra el contexto fuente."""
    def evaluar(
        self, payload: InputSchema, contenido: ContenidoAdaptadoSchema, contexto: ContextoRecuperado
    ) -> EvaluacionCalidadSchema: ...


class GeneradorMetadatos(Protocol):
    """NM-10: conceptos clave y tiempo estimado de estudio."""
    def generar(self, payload: InputSchema, contenido: ContenidoAdaptadoSchema) -> MetadatosSchema: ...


class Storage(Protocol):
    """NM-11: persiste original y paquete generado en OCI Object Storage."""
    def guardar(self, payload: InputSchema, paquete: dict) -> AlmacenamientoOCISchema: ...


class AdaptacionService:
    def __init__(
        self,
        contexto: ContextoProvider,
        generador: Generador,
        verificador: VerificadorFidelidad,
        metadatos: GeneradorMetadatos,
        storage: Storage,
    ) -> None:
        self._contexto = contexto
        self._generador = generador
        self._verificador = verificador
        self._metadatos = metadatos
        self._storage = storage

    def adaptar(self, payload: InputSchema) -> OutputSchema:
        rid = get_request_id()

        ctx = self._paso("contexto", VectorStoreError, lambda: self._contexto.obtener_contexto(payload))
        if not ctx.texto.strip():
            # Sin contexto anclado no se llama al LLM: evita contenido sin fuente.
            logger.warning("[%s] retrieval sin fragmentos sobre el umbral", rid)
            raise SinContextoRelevanteError()
        contenido = self._paso("generacion", LLMError, lambda: self._generador.generar(payload, ctx))
        evaluacion = self._paso("fidelidad", LLMError, lambda: self._verificador.evaluar(payload, contenido, ctx))
        metadatos = self._paso("metadatos", LLMError, lambda: self._metadatos.generar(payload, contenido))

        almacenamiento = self._persistir(payload, metadatos, contenido, evaluacion)

        logger.info(
            "[%s] adaptación OK formato=%s fuentes=%d oci=%s",
            rid, payload.formato_salida.value, len(ctx.fuentes), almacenamiento.status_upload,
        )
        return OutputSchema(
            status="exito",
            metadatos=metadatos,
            contenido_adaptado=contenido,
            evaluacion_calidad=evaluacion,
            almacenamiento_oci=almacenamiento,
        )

    @staticmethod
    def _paso(nombre: str, error_cls: type[AppError], fn):
        try:
            return fn()
        except AppError:
            raise
        except Exception as exc:
            logger.error(
                "[%s] falla en paso '%s' | %s",
                get_request_id(), nombre, error_sanitizado(exc),
            )
            raise error_cls() from exc

    def _persistir(self, payload, metadatos, contenido, evaluacion) -> AlmacenamientoOCISchema:
        paquete = {
            "metadatos": metadatos.model_dump(mode="json"),
            "contenido_adaptado": contenido.model_dump(mode="json"),
            "evaluacion_calidad": evaluacion.model_dump(mode="json"),
        }
        try:
            return self._storage.guardar(payload, paquete)
        except Exception as exc:
            logger.error(
                "[%s] falla al subir a OCI (no invalida la respuesta) | %s",
                get_request_id(), error_sanitizado(exc),
            )
            return AlmacenamientoOCISchema(
                bucket=settings.OCI_BUCKET_NAME,
                objeto_id=OBJETO_NO_PERSISTIDO,
                status_upload="error",
            )
