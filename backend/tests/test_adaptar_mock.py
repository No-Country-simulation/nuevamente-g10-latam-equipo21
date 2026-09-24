import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)

PAYLOAD_BASE = {
    "documento_titulo": "Introduccion a la Arquitectura de Redes VCN en OCI",
    "documento_contenido": "La Virtual Cloud Network (VCN) es una red privada...",
    "perfil_destinatario": "Principiante",
    "nicho_sector": "General",
    "nivel_detalle": "Didactico",
}

FORMATOS_Y_TIPO_ITEM = {
    "Flashcards": "flashcard",
    "Quiz": "quiz",
    "Tutorial": "tutorial",
    "Resumen_Ejecutivo": "resumen",
    "Guion_Clase": "guion",
}

ENDPOINT = f"{settings.API_V1_STR}/adaptar-contenido"


@pytest.fixture(autouse=True)
def _activar_mock(monkeypatch):
    # settings es un singleton cargado una sola vez al arrancar la app, así
    # que para togglear el feature flag en tests se parchea el atributo
    # directamente en vez de la variable de entorno (que ya no se relee).
    monkeypatch.setattr(settings, "USE_MOCK_LLM", True)


@pytest.mark.parametrize("formato,tipo_item_esperado", FORMATOS_Y_TIPO_ITEM.items())
def test_responde_estructura_completa_por_formato(formato, tipo_item_esperado):
    payload = {**PAYLOAD_BASE, "formato_salida": formato}
    resp = client.post(ENDPOINT, json=payload)

    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "exito"
    assert set(data.keys()) >= {
        "status",
        "metadatos",
        "contenido_adaptado",
        "evaluacion_calidad",
        "almacenamiento_oci",
    }
    assert data["metadatos"]["formato_generado"] == formato
    assert data["almacenamiento_oci"]["bucket"] == settings.OCI_BUCKET_NAME

    items = data["contenido_adaptado"]["items"]
    assert len(items) >= 1
    assert all(item["tipo_item"] == tipo_item_esperado for item in items)


def test_entrada_invalida_devuelve_shape_de_error_del_contrato():
    payload = {**PAYLOAD_BASE, "formato_salida": "Formato_Que_No_Existe"}
    resp = client.post(ENDPOINT, json=payload)

    assert resp.status_code == 422
    data = resp.json()
    assert data["status"] == "error"
    assert "codigo" in data["error"]
    assert "mensaje" in data["error"]


def test_mock_se_apaga_por_variable_de_entorno(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_LLM", False)
    payload = {**PAYLOAD_BASE, "formato_salida": "Flashcards"}

    resp = client.post(ENDPOINT, json=payload)

    # El endpoint real (NM-12) todavía no existe: se espera 501, no un mock.
    assert resp.status_code == 501
