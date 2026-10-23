"""Tests de la validación del enlace de cierre de sesión (NM-41)."""

import pytest

from components.sidebar import _logout_href


@pytest.mark.parametrize("valor", ["/salir", "/salir?x=1"])
def test_rutas_internas_se_aceptan(valor):
    assert _logout_href(valor) == valor


def test_caracteres_especiales_se_escapan_en_el_atributo():
    assert _logout_href('/salir?x="') == "/salir?x=&quot;"


@pytest.mark.parametrize(
    "valor",
    [
        "https://evil.example.com/salir",
        "//evil.example.com/salir",
        "javascript:alert(1)",
        "salir",
        "/salir con espacio",
        "/salir\\ruta",
        "\\\\evil.example.com",
        "",
        None,
    ],
)
def test_valores_inseguros_se_descartan(valor):
    assert _logout_href(valor) is None
