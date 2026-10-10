"""Selección mock/real del servicio de adaptación (USE_MOCK_LLM).

Se evalúa por petición, así el flag se cambia sin tocar el endpoint ni el
frontend (criterio de NM-12).
"""

from app.core.config import settings
from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.adaptacion_adapters import (
    construir_servicio_multiagente,
    construir_servicio_real,
)
from app.services.mock_adaptacion_service import construir_respuesta_mock



class MockAdaptacionService:
    def adaptar(self, payload: InputSchema) -> OutputSchema:
        return construir_respuesta_mock(payload)


def get_adaptacion_service():
    if settings.USE_MOCK_LLM:
        return MockAdaptacionService()
    if settings.USE_MULTIAGENT:
        return construir_servicio_multiagente()
    return construir_servicio_real()
