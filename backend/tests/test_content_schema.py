import pytest
from pydantic import ValidationError

from app.schemas.content import GuionItem, QuizItem, TutorialItem


def _quiz(opciones: list[str]) -> dict:
    return {
        "pregunta": "¿Qué es un índice?",
        "opciones": opciones,
        "respuesta_correcta": opciones[0],
        "justificacion": "La primera opción es correcta.",
    }


def test_quiz_exige_exactamente_cuatro_opciones():
    assert len(QuizItem.model_validate(_quiz(["A", "B", "C", "D"])).opciones) == 4

    with pytest.raises(ValidationError):
        QuizItem.model_validate(_quiz(["A", "B"]))

    with pytest.raises(ValidationError):
        QuizItem.model_validate(_quiz(["A", "B", "C", "D", "E"]))


def test_guion_exige_notas_visuales():
    payload = {
        "seccion": "Introducción",
        "tiempo_estimado_minutos": 5,
        "narracion": "Presentación del tema.",
    }

    with pytest.raises(ValidationError, match="notas_visuales"):
        GuionItem.model_validate(payload)


def test_tutorial_exige_codigo_ejemplo_pero_acepta_null():
    payload = {
        "paso_numero": 1,
        "titulo_paso": "Crear el índice",
        "contenido": "Ejecutar la sentencia indicada.",
    }

    with pytest.raises(ValidationError, match="codigo_ejemplo"):
        TutorialItem.model_validate(payload)

    item = TutorialItem.model_validate({**payload, "codigo_ejemplo": None})
    assert item.codigo_ejemplo is None


def test_items_rechazan_campos_ajenos_al_contrato():
    payload = {**_quiz(["A", "B", "C", "D"]), "campo_no_contrato": "valor"}

    with pytest.raises(ValidationError, match="campo_no_contrato"):
        QuizItem.model_validate(payload)
