"""Tests de las exportaciones del paquete educativo (NM-D5)."""

from components.download_exports import (
    anki_disponible,
    construir_anki_csv,
    construir_markdown,
    construir_pdf,
    nombre_base,
)


RESULTADO_FLASHCARDS = {
    "status": "exito",
    "metadatos": {
        "perfil_aplicado": "Principiante",
        "formato_generado": "Flashcards",
        "tiempo_estimado_estudio_minutos": 10,
        "conceptos_clave": ["VCN", "Subredes"],
        "prerrequisitos": ["Redes basicas"],
    },
    "contenido_adaptado": {
        "titulo": "Redes en la nube",
        "introduccion_contextualizada": "Introduccion",
        "items": [
            {
                "frente": "¿Qué es una VCN?",
                "dorso": "Una red privada",
                "pista_didactica": "Piensa en una oficina",
            },
            {
                "frente": "¿Qué es una subred?",
                "dorso": "Una porcion de la red",
                "pista_didactica": "Como un aula",
            },
        ],
    },
    "evaluacion_calidad": {
        "anclaje_fuente_score": 0.9,
        "claridad_pedagogica": "Alta",
        "observaciones": "ok",
    },
    "almacenamiento_oci": {
        "bucket": "b",
        "objeto_id": "o",
        "status_upload": "completado",
    },
}

RESULTADO_TUTORIAL = {
    **RESULTADO_FLASHCARDS,
    "metadatos": {
        **RESULTADO_FLASHCARDS["metadatos"],
        "formato_generado": "Tutorial",
    },
    "contenido_adaptado": {
        "titulo": "Tutorial",
        "introduccion_contextualizada": "Intro",
        "items": [
            {
                "paso_numero": 1,
                "titulo_paso": "Paso uno",
                "contenido": "Haz esto",
                "codigo_ejemplo": "print(1)",
            }
        ],
    },
}


def test_markdown_incluye_encabezados_y_items():
    markdown = construir_markdown(RESULTADO_FLASHCARDS)

    assert markdown.startswith("# Redes en la nube")
    assert "## Metadatos" in markdown
    assert "## Contenido" in markdown
    assert "¿Qué es una VCN?" in markdown
    assert "**Dorso:**" in markdown


def test_markdown_tutorial_incluye_bloque_de_codigo():
    markdown = construir_markdown(RESULTADO_TUTORIAL)

    assert "### Paso 1: Paso uno" in markdown
    assert "```" in markdown
    assert "print(1)" in markdown


def test_anki_solo_disponible_para_flashcards():
    assert anki_disponible(RESULTADO_FLASHCARDS) is True
    assert anki_disponible(RESULTADO_TUTORIAL) is False
    assert construir_anki_csv(RESULTADO_TUTORIAL) is None


def test_anki_csv_tiene_columnas_frente_y_dorso():
    contenido_csv = construir_anki_csv(RESULTADO_FLASHCARDS)
    lineas = contenido_csv.splitlines()

    assert lineas[0] == "frente,dorso"
    assert lineas[1] == "¿Qué es una VCN?,Una red privada"


def test_pdf_es_un_pdf_valido_y_paginable():
    datos = construir_pdf(RESULTADO_FLASHCARDS)

    assert datos.startswith(b"%PDF")
    assert datos.rstrip().endswith(b"%%EOF")


def test_pdf_de_tutorial_genera_bytes():
    datos = construir_pdf(RESULTADO_TUTORIAL)

    assert datos.startswith(b"%PDF")
    assert len(datos) > 0


def test_nombre_base_usa_tema_perfil_formato():
    base = nombre_base(RESULTADO_FLASHCARDS, titulo_documento="Redes VCN")

    assert base == "redes_vcn-principiante-flashcards"
