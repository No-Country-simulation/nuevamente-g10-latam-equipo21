"""Pruebas de regresión de las instrucciones de los prompts (NM-34).

Protegen que ciertas instrucciones no desaparezcan ni vuelvan a un estado
anterior. NO demuestran que el modelo deje de alucinar: eso solo se mide
con ejecuciones reales y con la verificación de fidelidad.
"""

import re
from pathlib import Path

import pytest

from app.services.prompts import personalizacion

PROMPTS_DIR = Path(personalizacion.__file__).parent

# Formas de voseo que NM-34 eliminó. Lista cerrada a propósito: un regex
# genérico daría falsos positivos con "está", "además", "información".
VOSEO = [
    "pensalo", "notá", "escribí", "tenés", "podés", "fijate", "mirá",
    "usá", "elegí", "agregá", "devolvé", "respondé", "generá", "incluí",
    "asegurate", "recordá", "considerá", "evitá", "mantené", "cuidá",
]
PATRON_VOSEO = re.compile(
    r"\b(" + "|".join(VOSEO) + r")\b", flags=re.IGNORECASE
)


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip().lower()


def _leer(nombre: str) -> str:
    return (PROMPTS_DIR / nombre).read_text(encoding="utf-8")


def _textos_personalizacion() -> list[tuple[str, str]]:
    textos: list[tuple[str, str]] = []
    for nombre in (
        "INSTRUCCIONES_PERFIL",
        "INSTRUCCIONES_NICHO",
        "INSTRUCCIONES_NIVEL_DETALLE",
    ):
        for clave, texto in getattr(personalizacion, nombre).items():
            textos.append((f"{nombre}[{clave}]", texto))
    for clave, entrada in personalizacion.INSTRUCCIONES_FORMATO.items():
        for subclave, texto in entrada.items():
            textos.append((f"INSTRUCCIONES_FORMATO[{clave}][{subclave}]", texto))
    return textos


ARCHIVOS_MD = sorted(p.name for p in PROMPTS_DIR.glob("*.md"))


def test_hay_prompts_que_verificar():
    assert ARCHIVOS_MD, "No se encontraron .md en la carpeta de prompts"


@pytest.mark.parametrize("nombre", ARCHIVOS_MD)
def test_md_sin_voseo(nombre):
    encontrados = PATRON_VOSEO.findall(_leer(nombre))
    assert not encontrados, f"Voseo en {nombre}: {encontrados}"


@pytest.mark.parametrize(
    "origen,texto",
    _textos_personalizacion(),
    ids=[origen for origen, _ in _textos_personalizacion()],
)
def test_personalizacion_sin_voseo(origen, texto):
    encontrados = PATRON_VOSEO.findall(texto)
    assert not encontrados, f"Voseo en {origen}: {encontrados}"


def test_adaptacion_base_mantiene_anclaje_al_contexto():
    texto = _normalizar(_leer("adaptacion_base.md"))
    assert "exclusivamente" in texto
    assert "contexto recuperado" in texto
    assert "explícitamente" in texto
    assert "inventar" in texto


def test_adaptacion_usuario_conserva_marcador_de_contexto():
    assert "{contexto_recuperado}" in _leer("adaptacion_usuario.md")


def test_resumen_ejecutivo_no_inventa_impacto_de_negocio():
    instrucciones = _normalizar(
        personalizacion.INSTRUCCIONES_FORMATO["Resumen_Ejecutivo"]["instrucciones"]
    )
    assert "no agregues beneficios que el documento no diga" in instrucciones
    assert (
        "el documento no analiza el impacto de negocio de este punto."
        in instrucciones
    )
    assert "solo si el documento no menciona" in instrucciones
