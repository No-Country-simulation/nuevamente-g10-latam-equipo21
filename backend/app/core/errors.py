"""Errores de dominio y su mapeo al shape del contrato (NM-01 / NM-12):
{"status": "error", "error": {"codigo": ..., "mensaje": ...}}.

El mensaje que llega al cliente es siempre el `mensaje` público de la
excepción: nunca trazas, ni credenciales, ni el texto de la excepción original
(esa queda solo en el log, junto con el request id).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.request_context import get_request_id, request_id_de
from app.core.log_sanitizer import error_sanitizado

logger = logging.getLogger("nuevamente.errors")


def error_body(codigo: str, mensaje: str) -> dict:
    return {"status": "error", "error": {"codigo": codigo, "mensaje": mensaje}}


class AppError(Exception):
    status_code: int = 500
    codigo: str = "ERROR_INTERNO"
    mensaje: str = "Ocurrió un error interno. Intenta nuevamente."

    def __init__(self, mensaje: str | None = None) -> None:
        self.mensaje = mensaje or type(self).mensaje
        super().__init__(self.mensaje)


class LLMError(AppError):
    status_code = 502
    codigo = "LLM_NO_DISPONIBLE"
    mensaje = "No se pudo generar el contenido en este momento. Intenta nuevamente."


class VectorStoreError(AppError):
    status_code = 502
    codigo = "VECTOR_STORE_NO_DISPONIBLE"
    mensaje = "No se pudo recuperar el contexto del documento. Intenta nuevamente."


class SinContextoRelevanteError(AppError):
    status_code = 422
    codigo = "SIN_CONTEXTO_RELEVANTE"
    mensaje = (
        "No se encontró contenido del documento suficientemente relevante para "
        "generar el material. Prueba con un documento más extenso o con otro título."
    )


class PipelineNoConfiguradaError(AppError):
    status_code = 501
    codigo = "PIPELINE_NO_CONFIGURADA"
    mensaje = "La pipeline de adaptación aún no está disponible en este entorno."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        causa = exc.__cause__ or exc.__context__
        logger.error(
            "[%s] %s (%s) en %s %s | causa: %s",
            request_id_de(request), exc.codigo, exc.status_code,
            request.method, request.url.path,
            error_sanitizado(causa) if causa else "n/a",
        )
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.codigo, exc.mensaje))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "[%s] ERROR_INTERNO no controlado en %s %s | %s",
            request_id_de(request), request.method, request.url.path,
            error_sanitizado(exc),
        )
        return JSONResponse(
            status_code=500,
            content=error_body(AppError.codigo, AppError.mensaje),
        )        