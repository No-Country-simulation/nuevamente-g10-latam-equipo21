import pytest
from pydantic import ValidationError

from app.schemas.enums import FormatoSalida
from app.schemas.output import OutputErrorSchema, OutputExitoSchema, validar_output


def _payload_salida(formato: str, items: list[dict]) -> dict:
    return {
        "status": "exito",
        "metadatos": {
            "perfil_aplicado": "Principiante",
            "formato_generado": formato,
            "tiempo_estimado_estudio_minutos": 10,
            "conceptos_clave": ["concepto"],
        },
        "contenido_adaptado": {
            "titulo": "Contenido adaptado",
            "introduccion_contextualizada": "Introducción",
            "items": items,
        },
        "evaluacion_calidad": {
            "anclaje_fuente_score": 0.9,
            "claridad_pedagogica": "Alta",
            "observaciones": "Contenido anclado.",
        },
        "almacenamiento_oci": {
            "bucket": "nuevamente-contenidos-educativos",
            "objeto_id": "salidas/contenido.json",
            "status_upload": "completado",
        },
    }


@pytest.mark.parametrize(
    ("formato", "item"),
    [
        (
            FormatoSalida.FLASHCARDS.value,
            {"frente": "F", "dorso": "D", "pista_didactica": "P"},
        ),
        (
            FormatoSalida.QUIZ.value,
            {
                "pregunta": "¿Pregunta?",
                "opciones": ["A", "B", "C", "D"],
                "respuesta_correcta": "A",
                "justificacion": "Justificación",
            },
        ),
        (
            FormatoSalida.TUTORIAL.value,
            {
                "paso_numero": 1,
                "titulo_paso": "Paso",
                "contenido": "Contenido",
                "codigo_ejemplo": None,
            },
        ),
        (
            FormatoSalida.RESUMEN_EJECUTIVO.value,
            {
                "punto_clave": "Punto",
                "descripcion": "Descripción",
                "impacto_negocio": "Impacto",
            },
        ),
        (
            FormatoSalida.GUION_CLASE.value,
            {
                "seccion": "Introducción",
                "tiempo_estimado_minutos": 5,
                "narracion": "Narración",
                "notas_visuales": "Mostrar un diagrama.",
            },
        ),
    ],
)
def test_acepta_items_del_formato_declarado(formato, item):
    salida = validar_output(_payload_salida(formato, [item]))

    assert isinstance(salida, OutputExitoSchema)
    assert salida.metadatos.formato_generado.value == formato


def test_rechaza_un_item_de_otro_formato():
    payload = _payload_salida(
        FormatoSalida.TUTORIAL.value,
        [{"frente": "F", "dorso": "D", "pista_didactica": "P"}],
    )

    with pytest.raises(ValidationError, match=r"posiciones \[0\]"):
        validar_output(payload)


def test_rechaza_una_lista_con_formatos_mezclados():
    payload = _payload_salida(
        FormatoSalida.FLASHCARDS.value,
        [
            {"frente": "F", "dorso": "D", "pista_didactica": "P"},
            {
                "paso_numero": 1,
                "titulo_paso": "Paso",
                "contenido": "Contenido",
                "codigo_ejemplo": None,
            },
        ],
    )

    with pytest.raises(ValidationError, match=r"posiciones \[1\]"):
        validar_output(payload)


def test_acepta_la_respuesta_de_error_del_contrato():
    salida = validar_output(
        {
            "status": "error",
            "error": {"codigo": "LLM_ERROR", "mensaje": "El proveedor no respondió."},
        }
    )

    assert isinstance(salida, OutputErrorSchema)
    assert salida.error.codigo == "LLM_ERROR"


def test_rechaza_campos_de_exito_en_una_respuesta_de_error():
    payload = {
        "status": "error",
        "error": {"codigo": "LLM_ERROR", "mensaje": "Fallo"},
        "contenido_adaptado": {"titulo": "No corresponde"},
    }

    with pytest.raises(ValidationError, match="contenido_adaptado"):
        validar_output(payload)
