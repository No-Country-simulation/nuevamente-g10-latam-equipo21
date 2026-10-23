"""NM-32: política determinista, sin llamadas a Gemini ni OCI."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.errors import DocumentoInsuficienteError
from app.schemas.input import InputSchema
from app.schemas.output import EvaluacionCalidadSchema
from app.services.quality_policy import aplicar_politica_calidad, validar_suficiencia_documento


@pytest.mark.parametrize("score,threshold,expected", [
    (0.69, 0.7, True), (0.7, 0.7, False), (0.8, 0.7, False),
    (0.8, 0.9, True), (0.0, 0.0, False), (1.0, 1.0, False),
])
def test_umbral_no_altera_el_score(score, threshold, expected):
    evaluacion = EvaluacionCalidadSchema(
        anclaje_fuente_score=score, claridad_pedagogica="Alta", observaciones="Prueba"
    )
    resultado = aplicar_politica_calidad(evaluacion, umbral=threshold)
    assert resultado.anclaje_fuente_score == score
    assert resultado.umbral_fidelidad == threshold
    assert resultado.requiere_revision is expected
    assert evaluacion.requiere_revision is None  # no muta la entrada


@pytest.mark.parametrize("field,value", [
    ("FIDELITY_SCORE_THRESHOLD", -0.1), ("FIDELITY_SCORE_THRESHOLD", 1.1),
    ("FIDELITY_SCORE_THRESHOLD", float("nan")),
    ("DOCUMENT_MIN_WORDS", 0), ("DOCUMENT_MIN_WORDS", -1),
])
def test_rechaza_configuracion_invalida(field, value):
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="test", USE_MOCK_LLM=True, _env_file=None, **{field: value})


@pytest.mark.parametrize("count,allowed", [(29, False), (30, True), (31, True)])
def test_minimo_configurable_inclusivo(monkeypatch, count, allowed):
    monkeypatch.setattr(settings, "DOCUMENT_MIN_WORDS", 30)
    payload = InputSchema(
        documento_titulo="Fuente de prueba", documento_contenido="palabra " * count,
        perfil_destinatario="Principiante", formato_salida="Quiz",
        nicho_sector="General", nivel_detalle="Didactico",
    )
    if allowed:
        validar_suficiencia_documento(payload)
    else:
        with pytest.raises(DocumentoInsuficienteError):
            validar_suficiencia_documento(payload)
