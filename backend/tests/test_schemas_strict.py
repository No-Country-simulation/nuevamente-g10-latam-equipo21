import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.dependencies import get_adaptacion_service


REQUEST_BRIEF = {
    "documento_titulo": "Introduccion a la Arquitectura de Redes VCN en OCI",
    "documento_contenido": (
        "La Virtual Cloud Network (VCN) es una red privada y personalizable en OCI."
    ),
    "perfil_destinatario": "Principiante",
    "formato_salida": "Flashcards",
    "nicho_sector": "General",
    "nivel_detalle": "Didactico",
}


def _output(*, formato: str = "Flashcards", items: list[dict] | None = None) -> dict:
    return {
        "status": "exito",
        "metadatos": {
            "perfil_aplicado": "Principiante",
            "formato_generado": formato,
            "tiempo_estimado_estudio_minutos": 5,
            "conceptos_clave": ["VCN"],
            "prerrequisitos": [],
        },
        "contenido_adaptado": {
            "titulo": "Redes VCN",
            "introduccion_contextualizada": "Introduccion",
            "items": items
            if items is not None
            else [
                {
                    "frente": "Que es una VCN?",
                    "dorso": "Una red.",
                    "pista_didactica": "Nube",
                }
            ],
        },
        "evaluacion_calidad": {
            "anclaje_fuente_score": 0.9,
            "claridad_pedagogica": "Alta",
            "observaciones": "Contenido anclado.",
        },
        "almacenamiento_oci": {
            "bucket": "nuevamente-contenidos-educativos",
            "objeto_id": "contenido.json",
            "status_upload": "completado",
        },
    }


def test_request_del_brief_sigue_validando():
    entrada = InputSchema.model_validate(REQUEST_BRIEF)

    assert entrada.formato_salida.value == "Flashcards"


def test_endpoint_rechaza_campo_desconocido_e_indica_su_nombre():
    test_app = create_app()
    test_app.dependency_overrides[get_adaptacion_service] = lambda: object()
    response = TestClient(test_app).post(
        "/api/v1/adaptar-contenido",
        json={**REQUEST_BRIEF, "campo_desconocido": "no permitido"},
    )

    assert response.status_code == 422
    assert "campo_desconocido" in response.json()["error"]["mensaje"]


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        (("metadatos", "tiempo_estimado_estudio_minutos"), "5"),
        (("evaluacion_calidad", "anclaje_fuente_score"), "0.9"),
    ],
)
def test_output_no_convierte_numeros_desde_string(ruta, valor):
    payload = _output()
    bloque, campo = ruta
    payload[bloque][campo] = valor

    with pytest.raises(ValidationError):
        OutputSchema.model_validate(payload)


def test_output_rechaza_items_que_no_corresponden_al_formato():
    quiz_item = {
        "pregunta": "Que es una VCN?",
        "opciones": ["Una red", "Un bucket"],
        "respuesta_correcta": "Una red",
        "justificacion": "El documento asi lo define.",
    }

    with pytest.raises(ValidationError, match="no corresponde al formato 'Flashcards'"):
        OutputSchema.model_validate(_output(items=[quiz_item]))


def test_esquema_anidado_rechaza_campos_desconocidos():
    payload = _output()
    payload["contenido_adaptado"]["items"][0]["campo_desconocido"] = "no permitido"

    with pytest.raises(ValidationError):
        OutputSchema.model_validate(payload)
