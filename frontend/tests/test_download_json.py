import json

import pytest

from components.download_json import (
    nombre_archivo,
    obtener_tema,
    serializar_paquete,
    slugify,
)

RESULTADO = {
    "status": "exito",
    "metadatos": {
        "perfil_aplicado": "Principiante",
        "formato_generado": "Flashcards",
        "conceptos_clave": ["Subredes", "Gestión"],
    },
    "contenido_adaptado": {"titulo": "Dominando Redes", "items": []},
}


def test_serializacion_se_relee_igual_y_conserva_tildes():
    datos = serializar_paquete(RESULTADO)
    texto = datos.decode("utf-8")
    assert json.loads(texto) == RESULTADO
    assert "Gestión" in texto
    assert "\\u00f3" not in texto


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Introducción a Redes en la Nube", "introduccion_a_redes_en_la_nube"),
        ("  ¿Qué es VCN?  ", "que_es_vcn"),
        ("Año/2026: A\\B", "ano_2026_a_b"),
        ("", ""),
        (None, ""),
        ("!!!", ""),
    ],
)
def test_slugify(entrada, esperado):
    assert slugify(entrada) == esperado


def test_slugify_limita_longitud_sin_guion_final():
    resultado = slugify("palabra " * 30, max_len=50)
    assert len(resultado) <= 50
    assert not resultado.endswith("_")


@pytest.mark.parametrize(
    "formato",
    ["Tutorial", "Flashcards", "Quiz", "Resumen_Ejecutivo", "Guion_Clase"],
)
@pytest.mark.parametrize(
    "perfil",
    [
        "Principiante",
        "Desarrollador_Junior_SemiSenior",
        "Lider_Tecnico_Arquitecto",
        "Gestor_Ejecutivo_No_Tecnico",
    ],
)
def test_nombre_archivo_valido(perfil, formato):
    nombre = nombre_archivo("Redes VCN en OCI", perfil, formato)
    assert nombre.endswith(".json")
    assert nombre.startswith("redes_vcn_en_oci-")
    assert slugify(perfil) in nombre and slugify(formato) in nombre
    assert not any(c in nombre for c in " /\\:")


def test_nombre_archivo_con_valores_vacios():
    assert nombre_archivo("", "", "") == "paquete-perfil-formato.json"


def test_obtener_tema_prioridad():
    assert obtener_tema(RESULTADO, "Mi título", "doc.pdf") == "Mi título"
    assert obtener_tema(RESULTADO, "  ", "informe.pdf") == "informe"
    assert obtener_tema(RESULTADO) == "Dominando Redes"
    assert obtener_tema({}) == ""
