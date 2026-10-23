from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


FRONTEND_DIR = Path(__file__).resolve().parents[1]

FORMAT_CASES = [
    (
        "Flashcards",
        {
            "frente": "¿Qué es una VCN?",
            "dorso": "Una red privada virtual.",
            "pista_didactica": "Pensá en una red aislada.",
        },
        ["¿Qué es una VCN?", "Una red privada virtual.", "Pensá en una red aislada."],
    ),
    (
        "Quiz",
        {
            "pregunta": "¿Para qué sirve una VCN?",
            "opciones": ["Aislar la red", "Editar imágenes"],
            "respuesta_correcta": "Aislar la red",
            "justificacion": "Permite controlar el tráfico.",
        },
        ["¿Para qué sirve una VCN?"],
    ),
    (
        "Tutorial",
        {
            "paso_numero": 1,
            "titulo_paso": "Crear la red",
            "contenido": "Definí el bloque CIDR.",
            "codigo_ejemplo": "print('Crear red')",
        },
        ["Paso 1", "Crear la red", "Definí el bloque CIDR.", "print('Crear red')"],
    ),
    (
        "Resumen_Ejecutivo",
        {
            "punto_clave": "Seguridad de red",
            "descripcion": "Separar el tráfico público y privado.",
            "impacto_negocio": "Reducir la exposición de datos.",
        },
        ["Seguridad de red", "Separar el tráfico público y privado.", "Reducir la exposición de datos."],
    ),
    (
        "Guion_Clase",
        {
            "seccion": "Introducción a redes",
            "tiempo_estimado_minutos": 2,
            "narracion": "Hoy conoceremos las redes virtuales.",
            "notas_visuales": "Mostrar un diagrama.",
        },
        ["Introducción a redes", "2 min", "Hoy conoceremos las redes virtuales.", "Mostrar un diagrama."],
    ),
]


def make_result(output_format, item, upload_status="error"):
    return {
        "status": "exito",
        "metadatos": {
            "perfil_aplicado": "Principiante",
            "formato_generado": output_format,
            "tiempo_estimado_estudio_minutos": 10,
            "conceptos_clave": ["Red virtual"],
            "prerrequisitos": [],
        },
        "contenido_adaptado": {
            "titulo": "Material de prueba",
            "introduccion_contextualizada": "Introducción del material.",
            "items": [item],
        },
        "evaluacion_calidad": {
            "anclaje_fuente_score": 0.95,
            "claridad_pedagogica": "Alta",
            "observaciones": "Contenido conectado a la fuente.",
            "umbral_fidelidad": 0.7,
            "requiere_revision": False,
            "afirmaciones_no_respaldadas": [],
        },
        "almacenamiento_oci": {
            "bucket": "bucket-prueba",
            "objeto_id": "material-prueba.json",
            "status_upload": upload_status,
        },
    }


def render_result(result):
    script = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
from components.package_result import render_package_result
render_package_result({result!r})
"""
    return AppTest.from_string(script, default_timeout=10).run()


def visible_text(app):
    element_types = [
        "header",
        "subheader",
        "markdown",
        "caption",
        "text",
        "code",
        "info",
    ]
    return "\n".join(
        str(element.value)
        for element_type in element_types
        for element in app.get(element_type)
    )


@pytest.mark.parametrize("output_format,item,expected_text", FORMAT_CASES)
def test_each_format_renders_content_and_common_header(
    output_format, item, expected_text
):
    app = render_result(make_result(output_format, item))

    assert not app.exception
    text = visible_text(app)
    assert "Material de prueba" in text
    assert "Introducción del material." in text
    assert "Red virtual" in text
    assert "Contenido conectado a la fuente." in text

    for expected in expected_text:
        assert expected in text

    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Tiempo estimado de estudio"] == "10 min"
    assert metrics["Anclaje a la fuente"] == "95%"
    assert metrics["Claridad pedagógica"] == "Alta"
    assert len(app.json) == 0


def test_quiz_shows_feedback_only_after_confirming_and_locks_answer():
    _, item, _ = FORMAT_CASES[1]
    app = render_result(make_result("Quiz", item))

    assert not app.exception
    assert app.radio[0].value is None
    assert app.radio[0].options == ["Aislar la red", "Editar imágenes"]
    assert len(app.info) == 0

    app.radio[0].set_value("Editar imágenes")
    app.run()

    assert not app.exception
    assert len(app.error) == 0
    assert len(app.info) == 0
    assert any(button.label == "Confirmar respuesta" for button in app.button)

    next(button for button in app.button if button.label == "Confirmar respuesta").click()
    app.run()

    assert not app.exception
    assert any("Incorrecto" in message.value for message in app.error)
    assert any("Permite controlar el tráfico." in message.value for message in app.info)
    assert app.radio[0].disabled
    assert any(button.label == "Reintentar" for button in app.button)


def test_quiz_score_and_retry_reset_answers():
    items = [
        {
            "pregunta": "¿Para qué sirve una VCN?",
            "opciones": ["Aislar la red", "Editar imágenes"],
            "respuesta_correcta": "Aislar la red",
            "justificacion": "Permite controlar el tráfico.",
        },
        {
            "pregunta": "¿Qué controla el tráfico?",
            "opciones": ["Security Lists", "Flashcards"],
            "respuesta_correcta": "Security Lists",
            "justificacion": "Las listas definen reglas de tráfico.",
        },
    ]
    result = make_result("Quiz", items[0])
    result["contenido_adaptado"]["items"] = items
    app = AppTest.from_string(
        f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
from components.package_result import render_package_result
render_package_result({result!r})
""",
        default_timeout=10,
    ).run()

    assert not app.exception
    app.radio[0].set_value("Editar imágenes")
    app.run()
    next(button for button in app.button if button.label == "Confirmar respuesta").click()
    app.run()

    app.radio[1].set_value("Security Lists")
    app.run()
    next(button for button in app.button if button.label == "Confirmar respuesta").click()
    app.run()

    assert not app.exception
    assert any("¡Correcto!" in message.value for message in app.success)
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Puntaje final"] == "50%"
    assert metrics["Aciertos"] == "1 de 2"
    assert len(app.button) == 1

    previous_widget_keys = [radio.key for radio in app.radio]
    app.button[0].click()
    app.run()

    assert not app.exception
    assert [radio.key for radio in app.radio] != previous_widget_keys
    assert [radio.value for radio in app.radio] == [None, None]
    assert "Puntaje final" not in {metric.label for metric in app.metric}
    assert app.session_state["quiz_answers"] == {}
    assert app.session_state["quiz_confirmed_answers"] == {}


def test_quiz_accepts_correct_answer_as_letter_with_prefixed_options():
    item = {
        "pregunta": "¿Cuál es la opción correcta?",
        "opciones": ["A) Primera opción", "B) Segunda opción"],
        "respuesta_correcta": "B",
        "justificacion": "La segunda opción es la correcta.",
    }
    app = render_result(make_result("Quiz", item))

    assert not app.exception
    app.radio[0].set_value("B) Segunda opción")
    app.run()
    next(
        button
        for button in app.button
        if button.label == "Confirmar respuesta"
    ).click()
    app.run()

    assert not app.exception
    assert any("¡Correcto!" in message.value for message in app.success)
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Puntaje final"] == "100%"
    assert metrics["Aciertos"] == "1 de 1"


def test_quiz_accepts_letter_and_answer_text_with_unprefixed_options():
    item = {
        "pregunta": "¿Cuál es la opción correcta?",
        "opciones": ["Primera opción", "Segunda opción"],
        "respuesta_correcta": "B) Segunda opción",
        "justificacion": "La segunda opción es la correcta.",
    }
    app = render_result(make_result("Quiz", item))

    assert not app.exception
    app.radio[0].set_value("Segunda opción")
    app.run()
    next(
        button
        for button in app.button
        if button.label == "Confirmar respuesta"
    ).click()
    app.run()

    assert not app.exception
    assert any("¡Correcto!" in message.value for message in app.success)
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Puntaje final"] == "100%"
    assert metrics["Aciertos"] == "1 de 1"


def test_quality_warnings_are_preserved_with_interactive_quiz():
    item = {
        "pregunta": "¿Cuál es la opción correcta?",
        "opciones": ["Primera opción", "Segunda opción"],
        "respuesta_correcta": "Segunda opción",
        "justificacion": "La segunda opción es la correcta.",
    }
    result = make_result("Quiz", item)
    result["evaluacion_calidad"].update(
        anclaje_fuente_score=0.69,
        requiere_revision=True,
        afirmaciones_no_respaldadas=[
            {"item": 1, "texto": "La respuesta no está respaldada."}
        ],
    )
    app = render_result(result)

    assert not app.exception
    assert any("requiere revisión" in message.value for message in app.warning)
    assert "Afirmación observada: La respuesta no está respaldada." in visible_text(app)
    assert ":orange[Por debajo del umbral de fidelidad (70%).]" in visible_text(app)
    assert app.radio[0].disabled is False


def test_loading_a_different_quiz_clears_previous_answers():
    first_result = make_result(
        "Quiz",
        {
            "pregunta": "Pregunta anterior",
            "opciones": ["Respuesta anterior", "Otra"],
            "respuesta_correcta": "Respuesta anterior",
            "justificacion": "Justificación anterior.",
        },
    )
    second_result = make_result(
        "Quiz",
        {
            "pregunta": "Pregunta nueva",
            "opciones": ["Respuesta nueva", "Otra"],
            "respuesta_correcta": "Respuesta nueva",
            "justificacion": "Justificación nueva.",
        },
    )
    app = AppTest.from_string(
        f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from components.package_result import render_package_result
st.session_state["quiz_result"] = {first_result!r}
if st.button("Cargar otro cuestionario"):
    st.session_state["quiz_result"] = {second_result!r}
render_package_result(st.session_state["quiz_result"])
""",
        default_timeout=10,
    ).run()

    app.radio[0].set_value("Otra")
    app.run()
    assert app.session_state["quiz_answers"] == {"1": "Otra"}

    app.button[0].click()
    app.run()

    assert not app.exception
    assert app.radio[0].value is None
    assert app.session_state["quiz_answers"] == {}
    assert app.session_state["quiz_confirmed_answers"] == {}
    assert not any("Justificación anterior." in message.value for message in app.info)


def test_completed_upload_shows_confirmation_bucket_and_object():
    _, item, _ = FORMAT_CASES[0]
    app = render_result(make_result("Flashcards", item, "completado"))

    assert not app.exception
    assert any("Contenido guardado en OCI." in message.value for message in app.success)
    text = visible_text(app)
    assert "Bucket: bucket-prueba" in text
    assert "Objeto: material-prueba.json" in text
    assert len(app.warning) == 0


def test_failed_upload_keeps_generated_content_and_shows_warning():
    _, item, _ = FORMAT_CASES[0]
    app = render_result(make_result("Flashcards", item, "error"))

    assert not app.exception
    assert "Una red privada virtual." in visible_text(app)
    assert any(
        "no se persistió en OCI" in message.value
        for message in app.warning
    )
    assert len(app.success) == 0


def test_prerequisites_are_listed_next_to_key_concepts():
    _, item, _ = FORMAT_CASES[0]
    result = make_result("Flashcards", item)
    result["metadatos"]["prerrequisitos"] = ["Direccionamiento IP", "Conceptos de redes"]
    app = render_result(result)

    assert not app.exception
    text = visible_text(app)
    assert "Prerrequisitos" in text
    assert "Direccionamiento IP" in text
    assert "Conceptos de redes" in text
    assert "Red virtual" in text  # los conceptos clave siguen visibles


def test_empty_prerequisites_hide_the_section():
    _, item, _ = FORMAT_CASES[0]
    app = render_result(make_result("Flashcards", item))  # prerrequisitos: []

    assert not app.exception
    assert "Prerrequisitos" not in visible_text(app)
