"""Política de presentación y suficiencia de la fuente (NM-32); no calcula el score."""

import re

from app.core.config import settings
from app.core.errors import DocumentoInsuficienteError
from app.schemas.input import InputSchema
from app.schemas.output import EvaluacionCalidadSchema


def validar_suficiencia_documento(payload: InputSchema) -> None:
    """Filtro de longitud, no evaluación semántica ni garantía de suficiencia."""
    palabras = re.findall(r"\b\w+\b", payload.documento_contenido, flags=re.UNICODE)
    if len(palabras) < settings.DOCUMENT_MIN_WORDS:
        raise DocumentoInsuficienteError(
            f"El documento no alcanza el mínimo de {settings.DOCUMENT_MIN_WORDS} palabras "
            f"para generar el formato {payload.formato_salida.value}. "
            "Agrega más información del documento original; no se generó contenido."
        )


def aplicar_politica_calidad(
    evaluacion: EvaluacionCalidadSchema, *, umbral: float | None = None
) -> EvaluacionCalidadSchema:
    minimo = settings.FIDELITY_SCORE_THRESHOLD if umbral is None else umbral
    return evaluacion.model_copy(update={
        "umbral_fidelidad": float(minimo),
        "requiere_revision": (
            evaluacion.anclaje_fuente_score < minimo
            or bool(evaluacion.afirmaciones_no_respaldadas)
        ),
    })
