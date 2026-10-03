import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.endpoints.adaptar import _EJEMPLO_RESPUESTA_200
from app.main import app
from app.schemas.output import OutputSchema

client = TestClient(app)

RUTA = "/api/v1/adaptar-contenido"
README = Path(__file__).resolve().parents[2] / "README.md"


def _ejemplo_422_del_readme() -> dict:
    contenido = README.read_text(encoding="utf-8")
    marcador = "Ejemplo de entrada inválida:"
    inicio_seccion = contenido.index(marcador)
    inicio_bloque = contenido.index("```json", inicio_seccion) + len("```json")
    fin_bloque = contenido.index("```", inicio_bloque)
    return json.loads(contenido[inicio_bloque:fin_bloque])


def test_ejemplo_200_cumple_el_contrato():
    OutputSchema.model_validate(_EJEMPLO_RESPUESTA_200)


def test_openapi_documenta_respuesta_200():
    spec = client.get("/api/v1/openapi.json").json()
    responses = spec["paths"][RUTA]["post"]["responses"]
    assert "example" in responses["200"]["content"]["application/json"]


def test_docs_redirige_a_swagger_versionado():
    response = client.get("/docs", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/api/v1/docs")


def test_ejemplo_422_del_readme_coincide_con_la_respuesta_real():
    payload = {
        "documento_titulo": "Titulo",
        "documento_contenido": "Contenido suficientemente largo",
        "perfil_destinatario": "PerfilQueNoExiste",
        "formato_salida": "Flashcards",
        "nicho_sector": "General",
        "nivel_detalle": "Didactico",
    }

    response = client.post(RUTA, json=payload)

    assert response.status_code == 422
    assert response.json() == _ejemplo_422_del_readme()


def test_422_se_registra_con_request_id_y_sin_contenido_del_documento(caplog):
    payload = {
        "documento_titulo": "Titulo",
        "documento_contenido": "TEXTO-SENSIBLE-DEL-DOCUMENTO",
        "perfil_destinatario": "PerfilQueNoExiste",
        "formato_salida": "Flashcards",
        "nicho_sector": "General",
        "nivel_detalle": "Didactico",
    }
    with caplog.at_level(logging.WARNING):
        response = client.post(RUTA, json=payload, headers={"X-Request-ID": "rid-test-422"})

    assert response.status_code == 422
    assert "rid-test-422" in caplog.text
    assert "perfil_destinatario" in caplog.text
    assert "TEXTO-SENSIBLE-DEL-DOCUMENTO" not in caplog.text
