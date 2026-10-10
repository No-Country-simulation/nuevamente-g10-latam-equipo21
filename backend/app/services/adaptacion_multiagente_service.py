"""Orquestador multi-agente de la pipeline de adaptación (NM-28).

Hermano de AdaptacionService: reutiliza contexto, metadatos y persistencia, y
reemplaza los pasos de generación (NM-08) y fidelidad (NM-09) por el grafo
LangGraph de NM-D1 (Redactor <-> Crítico). Se activa con USE_MULTIAGENT.

Política de errores: igual que AdaptacionService. Cualquier falla del grafo se
traduce a LLMError (HTTP 502) con el shape de error del contrato.
"""

import logging

from app.core.errors import LLMError, SinContextoRelevanteError, VectorStoreError
from app.core.log_sanitizer import error_sanitizado
from app.core.request_context import get_request_id
from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.adaptacion_adapters import (
    construir_consulta,
    documento_id_desde_contenido,
)
from app.services.adaptacion_service import AdaptacionService

logger = logging.getLogger("nuevamente.adaptacion")


class AdaptacionMultiAgenteService(AdaptacionService):
    """Reutiliza _paso y _persistir de AdaptacionService.

    `generador` y `verificador` no se usan: los reemplaza el grafo. Se reciben
    `grafo` ya compilado para poder inyectar un fake en los tests.
    """

    def __init__(self, contexto, metadatos, storage, grafo) -> None:
        super().__init__(
            contexto=contexto,
            generador=None,
            verificador=None,
            metadatos=metadatos,
            storage=storage,
        )
        self._grafo = grafo

    def _estado_inicial(self, payload: InputSchema, ctx) -> dict:
        return {
            "documento_id": documento_id_desde_contenido(payload.documento_contenido),
            "documento_titulo": payload.documento_titulo,
            "consulta_recuperacion": construir_consulta(
                payload.documento_titulo, payload.documento_contenido
            ),
            "perfil_destinatario": payload.perfil_destinatario.value,
            "formato_salida": payload.formato_salida.value,
            "nicho_sector": payload.nicho_sector.value,
            "nivel_detalle": payload.nivel_detalle.value,
            # Contexto ya recuperado con cobertura por ventanas (NM-22):
            # el nodo investigador lo detecta y no recupera de nuevo.
            "contexto_recuperado": ctx.texto,
        }

    def adaptar(self, payload: InputSchema) -> OutputSchema:
        rid = get_request_id()

        ctx = self._paso(
            "contexto", VectorStoreError, lambda: self._contexto.obtener_contexto(payload)
        )
        if not ctx.texto.strip():
            logger.warning("[%s] retrieval sin fragmentos sobre el umbral", rid)
            raise SinContextoRelevanteError()

        estado = self._paso(
            "grafo_multiagente",
            LLMError,
            lambda: self._grafo.invoke(self._estado_inicial(payload, ctx)),
        )
        contenido = estado["contenido_adaptado"]
        evaluacion = estado["evaluacion_calidad"]

        metadatos = self._paso(
            "metadatos", LLMError, lambda: self._metadatos.generar(payload, contenido)
        )
        almacenamiento = self._persistir(payload, metadatos, contenido, evaluacion)

        logger.info(
            "[%s] adaptación multiagente OK formato=%s iteraciones=%s score=%.2f oci=%s",
            rid,
            payload.formato_salida.value,
            estado.get("iteracion"),
            evaluacion.anclaje_fuente_score,
            almacenamiento.status_upload,
        )
        return OutputSchema(
            status="exito",
            metadatos=metadatos,
            contenido_adaptado=contenido,
            evaluacion_calidad=evaluacion,
            almacenamiento_oci=almacenamiento,
        )