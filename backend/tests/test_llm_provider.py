from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.services.llm_provider import LLMProvider, LLMProviderError, LLMTimeoutError


class _ProveedorDeJuguete:
    """Objeto mínimo que cumple el Protocol LLMProvider por duck typing (sin heredar de nada)."""

    def generate_structured(
        self,
        messages: list[BaseMessage],
        schema: type[BaseModel],
    ) -> BaseModel:
        return schema()


def test_cualquier_objeto_con_generate_structured_satisface_el_protocol():
    """
    LLMProvider es un Protocol runtime_checkable: cualquier implementación (Gemini u otra) debe
    poder verificarse contra él sin heredar de una clase base, habilitando el reemplazo de
    proveedor sin tocar el resto del pipeline.
    """
    assert isinstance(_ProveedorDeJuguete(), LLMProvider)


def test_un_objeto_sin_generate_structured_no_satisface_el_protocol():
    class _SinMetodoEsperado:
        pass

    assert not isinstance(_SinMetodoEsperado(), LLMProvider)


def test_llm_timeout_error_es_capturable_como_llm_provider_error():
    """
    Quien integre NM-08 debe poder capturar timeouts específicamente o cualquier fallo del
    proveedor de forma genérica, según necesite.
    """
    assert issubclass(LLMTimeoutError, LLMProviderError)
