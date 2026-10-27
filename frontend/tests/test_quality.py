import pytest

from utils.quality import requires_review


@pytest.mark.parametrize("quality,expected", [
    ({}, None),
    ({"requiere_revision": None, "umbral_fidelidad": None}, None),
    ({"requiere_revision": False}, False),
    ({"requiere_revision": True}, True),
    ({"requiere_revision": "false"}, None),
    ({"anclaje_fuente_score": 0.69, "umbral_fidelidad": 0.7, "requiere_revision": False}, True),
    ({"afirmaciones_no_respaldadas": [{"item": 0, "texto": "observada"}], "requiere_revision": False}, True),
])
def test_interpreta_la_politica_sin_aprobar_paquetes_antiguos(quality, expected):
    assert requires_review(quality) is expected
