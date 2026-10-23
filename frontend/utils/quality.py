"""Interpretación conservadora de la política de calidad enviada por la API."""


def requires_review(quality: dict) -> bool | None:
    if quality.get("afirmaciones_no_respaldadas"):
        return True

    score = quality.get("anclaje_fuente_score")
    threshold = quality.get("umbral_fidelidad")
    if score is not None and threshold is not None and score < threshold:
        return True

    flag = quality.get("requiere_revision")
    # Los paquetes anteriores no contienen la decisión de la política.
    return flag if isinstance(flag, bool) else None
