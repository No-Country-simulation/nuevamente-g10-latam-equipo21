import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.adaptacion_service import OBJETO_NO_PERSISTIDO
from app.services.document_identity import documento_id_desde_contenido

client = TestClient(app)

PAYLOAD_BASE = {
    "documento_titulo": "Introduccion a la Arquitectura de Redes VCN en OCI",
    "documento_contenido": "La Virtual Cloud Network (VCN) es una red privada...",
    "perfil_destinatario": "Principiante",
    "nicho_sector": "General",
    "nivel_detalle": "Didactico",
}

# Campos esperados por item según formato_salida, tomados de app.schemas.content.
# tipo_item no forma parte del contrato final: OutputSchema relaciona el tipo
# concreto del item con formato_generado sin exponer un discriminador.
FORMATOS_Y_CAMPOS_ITEM = {
    "Flashcards": {"frente", "dorso", "pista_didactica"},
    "Quiz": {"pregunta", "opciones", "respuesta_correcta", "justificacion"},
    "Tutorial": {"paso_numero", "titulo_paso", "contenido", "codigo_ejemplo"},
    "Resumen_Ejecutivo": {"punto_clave", "descripcion", "impacto_negocio"},
    "Guion_Clase": {"seccion", "tiempo_estimado_minutos", "narracion", "notas_visuales"},
}

ENDPOINT = f"{settings.API_V1_STR}/adaptar-contenido"


@pytest.fixture(autouse=True)
def _activar_mock(monkeypatch):
    # settings es un singleton cargado una sola vez al arrancar la app, así
    # que para togglear el feature flag en tests se parchea el atributo
    # directamente en vez de la variable de entorno (que ya no se relee).
    monkeypatch.setattr(settings, "USE_MOCK_LLM", True)


@pytest.mark.parametrize("formato,campos_item_esperados", FORMATOS_Y_CAMPOS_ITEM.items())
def test_responde_estructura_completa_por_formato(formato, campos_item_esperados):
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
    assert data["metadatos"]["perfil_aplicado"] == PAYLOAD_BASE["perfil_destinatario"]

    assert data["almacenamiento_oci"]["bucket"] == settings.OCI_BUCKET_NAME
    assert data["almacenamiento_oci"]["status_upload"] == "error"
    assert data["almacenamiento_oci"]["objeto_id"] == "mock-no-persistido"

    assert 0 <= data["evaluacion_calidad"]["anclaje_fuente_score"] <= 1
    assert data["evaluacion_calidad"]["claridad_pedagogica"] in {"Alta", "Media", "Baja"}

    assert data["contenido_adaptado"]["titulo"]
    assert data["contenido_adaptado"]["introduccion_contextualizada"]

    items = data["contenido_adaptado"]["items"]
    assert len(items) >= 1
    for item in items:
        assert campos_item_esperados <= set(item.keys())
        assert "tipo_item" not in item


def test_mock_quiz_incluye_cuatro_preguntas_con_respuestas_validas():
    payload = {**PAYLOAD_BASE, "formato_salida": "Quiz"}
    resp = client.post(ENDPOINT, json=payload)

    assert resp.status_code == 200
    items = resp.json()["contenido_adaptado"]["items"]
    assert len(items) == 4
    assert len({item["pregunta"] for item in items}) == 4
    assert all(item["respuesta_correcta"] in item["opciones"] for item in items)


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
    monkeypatch.setattr(settings, "USE_MULTIAGENT", False)
    payload = {**PAYLOAD_BASE, "formato_salida": "Flashcards"}

    from app.services.mock_adaptacion_service import construir_respuesta_mock

    llamados = []

    class ServicioRealFalso:
        def adaptar(self, payload_):
            llamados.append(payload_)
            return construir_respuesta_mock(payload_)

    monkeypatch.setattr(
        "app.services.dependencies.construir_servicio_real", lambda: ServicioRealFalso()
    )
    resp = client.post(ENDPOINT, json=payload)

    # Con USE_MOCK_LLM=false el endpoint delega en el servicio real, no en el mock.
    assert resp.status_code == 200 and len(llamados) == 1


def test_mock_no_reporta_una_subida_exitosa_a_oci():
    payload = {**PAYLOAD_BASE, "formato_salida": "Flashcards"}
    data = client.post(ENDPOINT, json=payload).json()
    almacenamiento = data["almacenamiento_oci"]

    # No hubo subida: nunca debe figurar como completada.
    assert almacenamiento["status_upload"] == "error"
    # El identificador señala el origen simulado y se distingue del flujo real.
    assert almacenamiento["objeto_id"] == "mock-no-persistido"
    assert almacenamiento["objeto_id"] != OBJETO_NO_PERSISTIDO
    assert almacenamiento["documento_id"] == documento_id_desde_contenido(
        PAYLOAD_BASE["documento_contenido"]
    )


def test_mock_tutorial_incluye_prerrequisitos():
    payload = {**PAYLOAD_BASE, "formato_salida": "Tutorial"}
    data = client.post(ENDPOINT, json=payload).json()

    prerrequisitos = data["metadatos"]["prerrequisitos"]
    assert len(prerrequisitos) >= 1
    assert all(isinstance(p, str) and p for p in prerrequisitos)


def test_mock_flashcards_devuelve_prerrequisitos_vacios():
    payload = {**PAYLOAD_BASE, "formato_salida": "Flashcards"}
    data = client.post(ENDPOINT, json=payload).json()

    assert data["metadatos"]["prerrequisitos"] == []