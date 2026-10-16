import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.request_context import RequestIdMiddleware, get_request_id

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.API_V1_STR)
    register_exception_handlers(application)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errores = exc.errors()
        primer_error = errores[0] if errores else {}
        campo = ".".join(str(p) for p in primer_error.get("loc", []) if p != "body")

        # Se registra solo la ubicación y el tipo de cada error. Nunca `input`
        # ni `msg`: el body incluye `documento_contenido`, que puede ser grande
        # o sensible.
        resumen = [
            {
                "campo": ".".join(str(p) for p in e.get("loc", []) if p != "body"),
                "tipo": e.get("type", "desconocido"),
            }
            for e in errores
        ]
        logger.warning(
            "[%s] validación 422 en %s %s: %s",
            get_request_id(), request.method, request.url.path, resumen,
        )

        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error": {
                    "codigo": "ENTRADA_INVALIDA",
                    "mensaje": (
                        f"Campo '{campo}': {primer_error.get('msg', 'valor inválido')}"
                        if campo
                        else primer_error.get("msg", "La solicitud no cumple con el esquema esperado.")
                    ),
                },
            },
        )

    @application.get("/docs", include_in_schema=False)
    async def docs_redirect() -> RedirectResponse:
        """Atajo: el ticket pide Swagger en /docs; la UI real vive bajo el prefijo versionado."""
        return RedirectResponse(url=f"{settings.API_V1_STR}/docs")

    @application.get("/", tags=["Root"], summary="Raíz informativa de la API")
    async def root():
        return {
            "message": f"Bienvenido a {settings.PROJECT_NAME}",
            "docs": f"{settings.API_V1_STR}/docs",
            "health": f"{settings.API_V1_STR}/health",
        }

    return application


app = create_app()
