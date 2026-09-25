"""
Pruebas del servicio de recuperación semántica (NM-06).

Se usa un `VectorStoreFake` en memoria: la capa bajo prueba nunca toca ChromaDB ni un modelo de
embeddings real, lo que mantiene los tests deterministas y sin dependencias externas.
"""

import dataclasses

import pytest

from app.core.config import settings
from app.services.retrieval_service import (
    contar_tokens_aproximado,
    ensamblar_contexto,
    recuperar_contexto,
)
from app.services.vector_store import FragmentoRecuperado, VectorStore


class VectorStoreFake:
    """Implementación en memoria de `VectorStore` para tests."""

    def __init__(self, fragmentos: list[FragmentoRecuperado]) -> None:
        self._fragmentos = list(fragmentos)
        self.llamadas: list[dict] = []

    def buscar_similares(
        self, *, texto_consulta: str, top_k: int, documento_id: str | None = None
    ) -> list[FragmentoRecuperado]:
        self.llamadas.append(
            {"texto_consulta": texto_consulta, "top_k": top_k, "documento_id": documento_id}
        )
        encontrados = [
            fragmento
            for fragmento in self._fragmentos
            if documento_id is None or fragmento.documento_id == documento_id
        ]
        encontrados.sort(key=lambda fragmento: fragmento.score, reverse=True)
        return encontrados[:top_k]


def _fragmento(
    chunk_id: str,
    *,
    documento_id: str = "doc-1",
    texto: str = "texto de prueba",
    score: float = 0.9,
    metadatos: dict | None = None,
) -> FragmentoRecuperado:
    return FragmentoRecuperado(
        chunk_id=chunk_id,
        documento_id=documento_id,
        texto=texto,
        score=score,
        metadatos=metadatos or {},
    )


def test_filtra_por_umbral_y_ordena_descendente():
    """
    Solo se devuelven fragmentos con score >= umbral, ordenados de mayor a menor relevancia.
    """
    store = VectorStoreFake(
        [
            _fragmento("c-bajo", score=0.20),
            _fragmento("c-alto", score=0.95),
            _fragmento("c-medio", score=0.60),
        ]
    )

    resultado = recuperar_contexto(consulta="consulta", vector_store=store, umbral=0.5)

    assert [fragmento.chunk_id for fragmento in resultado] == ["c-alto", "c-medio"]


def test_score_igual_al_umbral_se_incluye():
    """
    El umbral es inclusivo: un fragmento con score exactamente igual al umbral se considera relevante.
    """
    store = VectorStoreFake([_fragmento("c-limite", score=0.5)])

    resultado = recuperar_contexto(consulta="consulta", vector_store=store, umbral=0.5)

    assert [fragmento.chunk_id for fragmento in resultado] == ["c-limite"]


def test_sin_coincidencias_sobre_umbral_devuelve_vacio():
    """
    Si ningún fragmento supera el umbral, se devuelve una lista vacía y no fragmentos irrelevantes.
    """
    store = VectorStoreFake([_fragmento("c1", score=0.1), _fragmento("c2", score=0.2)])

    resultado = recuperar_contexto(consulta="consulta", vector_store=store, umbral=0.8)

    assert resultado == []


def test_respeta_top_k_y_lo_propaga_al_store():
    """
    La búsqueda se acota a `top_k` y ese límite se delega al almacén vectorial.
    """
    store = VectorStoreFake([_fragmento(f"c{i}", score=0.9) for i in range(5)])

    resultado = recuperar_contexto(consulta="consulta", vector_store=store, top_k=2, umbral=0.5)

    assert len(resultado) == 2
    assert store.llamadas[0]["top_k"] == 2


def test_restringe_busqueda_a_un_documento():
    """
    Con `documento_id`, la búsqueda solo devuelve fragmentos de ese documento.
    """
    store = VectorStoreFake(
        [
            _fragmento("c1", documento_id="doc-1", score=0.9),
            _fragmento("c2", documento_id="doc-2", score=0.8),
        ]
    )

    resultado = recuperar_contexto(
        consulta="consulta", vector_store=store, umbral=0.5, documento_id="doc-2"
    )

    assert [fragmento.documento_id for fragmento in resultado] == ["doc-2"]
    assert store.llamadas[0]["documento_id"] == "doc-2"


def test_usa_defaults_de_configuracion(monkeypatch):
    """
    Sin argumentos explícitos, `top_k` y `umbral` se toman de la configuración de la aplicación.
    """
    monkeypatch.setattr(settings, "RETRIEVAL_TOP_K", 1)
    monkeypatch.setattr(settings, "RETRIEVAL_SCORE_THRESHOLD", 0.99)
    store = VectorStoreFake(
        [_fragmento("c1", score=0.995), _fragmento("c2", score=0.999)]
    )

    resultado = recuperar_contexto(consulta="consulta", vector_store=store)

    assert len(resultado) == 1
    assert store.llamadas[0]["top_k"] == 1


def test_ensamblar_contexto_incluye_referencia_y_metadatos():
    """
    Cada fragmento se antepone con su referencia de origen (documento, chunk y metadatos) para
    permitir citar la fuente.
    """
    fragmento = _fragmento(
        "c1",
        documento_id="doc-9",
        texto="contenido relevante",
        metadatos={"pagina": 3, "seccion": "introduccion"},
    )

    contexto = ensamblar_contexto([fragmento], contar_tokens=len)

    assert "documento=doc-9" in contexto
    assert "chunk=c1" in contexto
    assert "pagina=3" in contexto
    assert "seccion=introduccion" in contexto
    assert "contenido relevante" in contexto


def test_ensamblar_contexto_trunca_por_relevancia():
    """
    Al superar el límite de tokens se conserva el prefijo más relevante y se descarta el resto.
    """
    fragmentos = [
        _fragmento("c1", texto="primero", score=0.9),
        _fragmento("c2", texto="segundo", score=0.8),
        _fragmento("c3", texto="tercero", score=0.7),
    ]

    esperado = ensamblar_contexto(fragmentos[:2], contar_tokens=len)
    truncado = ensamblar_contexto(
        fragmentos, max_tokens=len(esperado), contar_tokens=len
    )

    assert truncado == esperado
    assert "tercero" not in truncado


def test_ensamblar_contexto_sin_coincidencias_devuelve_cadena_vacia():
    """Sin fragmentos, el contexto ensamblado es una cadena vacía."""
    assert ensamblar_contexto([], contar_tokens=len) == ""


def test_ensamblar_contexto_usa_default_de_configuracion(monkeypatch):
    """
    Sin `max_tokens` explícito, el límite se toma de la configuración de la aplicación.
    """
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_CONTEXT_TOKENS", 0)

    contexto = ensamblar_contexto([_fragmento("c1")], contar_tokens=len)

    assert contexto == ""


def test_contar_tokens_aproximado():
    """La estimación por defecto crece con la longitud del texto."""
    assert contar_tokens_aproximado("") == 0
    assert contar_tokens_aproximado("cuatro") == 2


def test_vector_store_fake_es_conforme_al_protocolo():
    """El fake satisface el Protocol `VectorStore` (contrato que deberá cumplir la implementación de NM-05)."""
    assert isinstance(VectorStoreFake([]), VectorStore)


def test_fragmento_recuperado_es_inmutable():
    """`FragmentoRecuperado` es inmutable para evitar mutaciones accidentales del resultado."""
    fragmento = _fragmento("c1")

    with pytest.raises(dataclasses.FrozenInstanceError):
        fragmento.score = 0.1  # type: ignore[misc]
