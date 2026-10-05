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
        ["¿Para qué sirve una VCN?", "Editar imágenes", "Permite controlar el tráfico."],
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
    assert metrics["Anclaje a la fuente"] == "0.95"
    assert metrics["Claridad pedagógica"] == "Alta"
    assert len(app.json) == 0


def test_quiz_answer_and_justification_are_inside_closed_expander():
    _, item, _ = FORMAT_CASES[1]
    app = render_result(make_result("Quiz", item))

    assert not app.exception
    expander = app.expander[0]
    assert expander.label == "Ver respuesta y justificación"
    assert expander.proto.expanded is False

    text = "\n".join(element.value for element in expander.markdown)
    assert "Respuesta correcta" in text
    assert "Aislar la red" in text
    assert "Justificación" in text
    assert "Permite controlar el tráfico." in text


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
        "no pudo almacenarse en OCI" in message.value
        for message in app.warning
    )
    assert len(app.success) == 0