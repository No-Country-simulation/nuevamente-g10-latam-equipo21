"""NM-21: el sobre de error {"status": "error", "error": {codigo, mensaje}} se aplica
en todos los endpoints, incluso para errores que llegan como HTTPException (404/405)."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.main import app
from app.schemas.output import ErrorResponseSchema


client = TestClient(app, raise_server_exceptions=False)


def test_ruta_inexistente_devuelve_el_sobre_de_error():
    response = client.get("/api/v1/ruta-que-no-existe")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "NO_ENCONTRADO"
    assert body["error"]["mensaje"]


def test_metodo_no_permitido_devuelve_el_sobre_de_error():
    # /adaptar-contenido solo acepta POST.
    response = client.get("/api/v1/adaptar-contenido")

    assert response.status_code == 405
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "METODO_NO_PERMITIDO"


def test_el_modelo_del_sobre_acepta_el_cuerpo_del_handler():
    cuerpo = {"status": "error", "error": {"codigo": "X", "mensaje": "y"}}

    modelo = ErrorResponseSchema.model_validate(cuerpo)

    assert modelo.error.codigo == "X"
    assert modelo.error.mensaje == "y"


SECRETO = "secreto-interno-no-debe-salir"


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_http_5xx_no_expone_el_detalle_interno(status_code):
    """Un HTTPException 5xx no debe filtrar el detalle técnico al cliente (solo al log)."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise HTTPException(
            status_code=status_code,
            detail=f"detalle interno api_key={SECRETO}",
        )

    app_client = TestClient(app, raise_server_exceptions=False)
    response = app_client.get("/boom")

    assert response.status_code == status_code
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["codigo"] == "ERROR_INTERNO"
    assert SECRETO not in response.text
    assert "detalle interno" not in response.text
