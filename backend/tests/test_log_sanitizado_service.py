import inspect
import logging
from types import SimpleNamespace

from app.core.errors import PipelineNoConfiguradaError
from app.services import adaptacion_service as modulo

CLAVE_FALSA = "AIzaSyA1234567890abcdefghijklmnopqrstuv"

# Se localiza la clase del servicio sin depender de su nombre exacto.
SERVICIO = next(
    c
    for _, c in inspect.getmembers(modulo, inspect.isclass)
    if c.__module__ == modulo.__name__ and hasattr(c, "_paso")
)


def test_paso_no_filtra_credenciales_en_logs(caplog):
    def falla():
        raise RuntimeError(f"fallo con key={CLAVE_FALSA}")

    with caplog.at_level(logging.ERROR):
        try:
            SERVICIO._paso("generacion", PipelineNoConfiguradaError, falla)
        except PipelineNoConfiguradaError:
            pass

    assert "generacion" in caplog.text
    assert CLAVE_FALSA not in caplog.text


def test_persistir_no_filtra_credenciales_y_no_invalida_la_respuesta(caplog):
    class StorageQueFalla:
        def guardar(self, payload, paquete):
            raise RuntimeError(f"fallo OCI con key={CLAVE_FALSA}")

    modelo_falso = SimpleNamespace(model_dump=lambda mode="json": {})
    servicio = object.__new__(SERVICIO)
    servicio._storage = StorageQueFalla()

    with caplog.at_level(logging.ERROR):
        almacenamiento = servicio._persistir(None, modelo_falso, modelo_falso, modelo_falso)

    assert almacenamiento.status_upload == "error"
    assert CLAVE_FALSA not in caplog.text
