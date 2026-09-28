import pytest
from pydantic import ValidationError

from app.schemas.input import InputSchema


def _entrada_valida() -> dict:
    return {
        "documento_titulo": "Índices en bases de datos",
        "documento_contenido": "Un índice acelera las búsquedas en una base de datos.",
        "perfil_destinatario": "Principiante",
        "formato_salida": "Flashcards",
        "nicho_sector": "General",
        "nivel_detalle": "Introductorio",
    }


def test_acepta_los_seis_campos_y_enums_del_contrato():
    entrada = InputSchema.model_validate(_entrada_valida())

    assert entrada.perfil_destinatario.value == "Principiante"
    assert entrada.formato_salida.value == "Flashcards"


def test_enum_invalido_indica_el_campo_y_los_valores_permitidos():
    payload = {**_entrada_valida(), "perfil_destinatario": "Invalido"}

    with pytest.raises(ValidationError) as exc_info:
        InputSchema.model_validate(payload)

    error = exc_info.value.errors()[0]
    assert error["loc"] == ("perfil_destinatario",)
    assert "Principiante" in error["msg"]
    assert "Lider_Tecnico_Arquitecto" in error["msg"]


def test_campo_obligatorio_faltante_indica_el_campo():
    payload = _entrada_valida()
    del payload["nicho_sector"]

    with pytest.raises(ValidationError) as exc_info:
        InputSchema.model_validate(payload)

    assert exc_info.value.errors()[0]["loc"] == ("nicho_sector",)
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_rechaza_campos_ajenos_al_contrato():
    payload = {**_entrada_valida(), "campo_no_contrato": "valor"}

    with pytest.raises(ValidationError, match="campo_no_contrato"):
        InputSchema.model_validate(payload)


def test_rechaza_coercion_de_tipos():
    payload = {**_entrada_valida(), "documento_titulo": 123}

    with pytest.raises(ValidationError, match="documento_titulo"):
        InputSchema.model_validate(payload)
