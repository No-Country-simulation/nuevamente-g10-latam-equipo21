import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import PipelineNoConfiguradaError, register_exception_handlers
from app.core.request_context import RequestIdMiddleware

CLAVE_FALSA = "AIzaSyA1234567890abcdefghijklmnopqrstuv"


def _cliente() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    @app.get("/error-dominio")
    def error_dominio():
        raise PipelineNoConfiguradaError() from RuntimeError(f"fallo con key={CLAVE_FALSA}")

    @app.get("/error-inesperado")
    def error_inesperado():
        raise RuntimeError(f"fallo con key={CLAVE_FALSA}")

    return TestClient(app, raise_server_exceptions=False)


def test_error_de_dominio_no_filtra_credenciales_en_logs(caplog):
    with caplog.at_level(logging.ERROR):
        response = _cliente().get("/error-dominio", headers={"X-Request-ID": "rid-dominio"})

    assert response.status_code == 501
    assert "rid-dominio" in caplog.text
    assert CLAVE_FALSA not in caplog.text


def test_error_inesperado_no_filtra_credenciales_en_logs(caplog):
    with caplog.at_level(logging.ERROR):
        response = _cliente().get("/error-inesperado", headers={"X-Request-ID": "rid-inesperado"})

    assert response.status_code == 500
    assert "rid-inesperado" in caplog.text
    assert CLAVE_FALSA not in caplog.text
