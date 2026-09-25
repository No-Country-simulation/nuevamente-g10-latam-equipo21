"""
Pruebas de la verificación de fidelidad (NM-09).

Se usan un almacén vectorial y un verificador (LLM) falsos: la capa bajo prueba nunca toca ChromaDB,
embeddings ni Gemini. Estas pruebas cubren el cálculo del score, el cableado de la evidencia y el
registro en logs; no miden qué tan bien juzga un modelo real.
"""

import logging

import pytest

from app.core.config import settings
from app.services import fidelity_service
from app.services.fidelity_service import calcular_score, evaluar_fidelidad
from app.services.llm_provider import LLMProviderError, LLMTimeoutError
from app.services.vector_store import FragmentoRecuperado

_DOC = "doc-cache"
_LOGGER = "app.services.fidelity_service"

_TEXTO_0 = "Una caché guarda copias de datos de acceso frecuente para reducir la latencia."
_TEXTO_1 = "El TTL hace que cada dato expire pasado un tiempo definido."

_EVIDENCIA = [
    FragmentoRecuperado(
        chunk_id="doc-cache:0", documento_id=_DOC, texto=_TEXTO_0, score=0.9, metadatos={"pagina": 1}
    ),
    FragmentoRecuperado(
        chunk_id="doc-cache:1", documento_id=_DOC, texto=_TEXTO_1, score=0.8, metadatos={"pagina": 2}
    ),
]
_DE_OTRO_DOCUMENTO = FragmentoRecuperado(
    chunk_id="otro:0", documento_id="otro", texto="Texto de otro documento.", score=0.95, metadatos={}
)


class VectorStoreFake:
    """Almacén vectorial en memoria que registra las consultas que recibe."""

    def __init__(self, fragmentos):
        self._fragmentos = list(fragmentos)
        self.llamadas: list[dict] = []

    def buscar_similares(self, *, texto_consulta, top_k, documento_id=None):
        self.llamadas.append(
            {"texto_consulta": texto_consulta, "top_k": top_k, "documento_id": documento_id}
        )
        encontrados = [
            fragmento
            for fragmento in self._fragmentos
            if documento_id is None or fragmento.documento_id == documento_id
        ]
        return encontrados[:top_k]


class VerificadorFake:
    """Devuelve una respuesta fija y guarda los mensajes que recibió."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.mensajes = None

    def generate_json(self, messages):
        self.mensajes = messages
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


class VerificadorPorEvidencia:
    """Marca una afirmación como respaldada solo si su texto aparece en la evidencia recibida."""

    def __init__(self, afirmaciones):
        self.afirmaciones = afirmaciones

    def generate_json(self, messages):
        # La evidencia va antes de "Contenido generado:" en el mensaje de usuario.
        evidencia = messages[1].content.split("Contenido generado:")[0].lower()
        return {
            "afirmaciones": [
                {"item": 1, "texto": afirmacion, "respaldada": afirmacion.lower() in evidencia}
                for afirmacion in self.afirmaciones
            ],
            "claridad_pedagogica": "Alta",
            "observaciones": "Verificación de prueba.",
        }


def _contenido(*dorsos):
    return {
        "titulo": "Cachés",
        "introduccion_contextualizada": "Vamos a ver qué es una caché.",
        "items": [
            {"frente": f"Pregunta {i}", "dorso": dorso, "pista_didactica": "pista"}
            for i, dorso in enumerate(dorsos, start=1)
        ],
    }


def _respuesta(respaldadas, claridad="Alta", observaciones="Observación concreta."):
    return {
        "afirmaciones": [
            {"item": 1, "texto": f"afirmación {i}", "respaldada": respaldada}
            for i, respaldada in enumerate(respaldadas)
        ],
        "claridad_pedagogica": claridad,
        "observaciones": observaciones,
    }


def _evaluar(verificador, *, contenido=None, store=None, **extra):
    return evaluar_fidelidad(
        documento_id=_DOC,
        contenido_adaptado=contenido or _contenido("uno", "dos"),
        vector_store=store or VectorStoreFake(_EVIDENCIA),
        llm_provider=verificador,
        **extra,
    )


def _avisos_de_fidelidad(caplog):
    return [registro for registro in caplog.records if registro.name == _LOGGER]


def test_devuelve_el_bloque_evaluacion_calidad_del_contrato():
    """Criterios 1 y 2: score entre 0 y 1, claridad válida y observaciones con texto."""
    resultado = _evaluar(VerificadorFake(_respuesta([True, True, False], "Media", "El item 2 no está respaldado.")))

    assert set(resultado) == {"anclaje_fuente_score", "claridad_pedagogica", "observaciones"}
    assert isinstance(resultado["anclaje_fuente_score"], float)
    assert 0.0 <= resultado["anclaje_fuente_score"] <= 1.0
    assert resultado["claridad_pedagogica"] in ("Alta", "Media", "Baja")
    assert resultado["observaciones"] == "El item 2 no está respaldado."


def test_el_score_es_la_proporcion_de_afirmaciones_respaldadas():
    assert _evaluar(VerificadorFake(_respuesta([True, True, True, False])))["anclaje_fuente_score"] == 0.75
    assert calcular_score([True, False, False]) == 0.33
    assert calcular_score([True, True]) == 1.0


def test_sin_afirmaciones_el_score_es_cero_y_se_registra(caplog):
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        resultado = _evaluar(VerificadorFake(_respuesta([])))

    assert resultado["anclaje_fuente_score"] == 0.0
    assert _avisos_de_fidelidad(caplog)


def test_contenido_con_afirmaciones_ausentes_puntua_menos_que_el_anclado():
    """
    Criterio 4: con la misma evidencia, un contenido con una afirmación que el documento no dice
    obtiene un score menor que uno plenamente respaldado.
    """
    respaldadas = ["guarda copias de datos de acceso frecuente", "cada dato expire pasado un tiempo"]
    inventada = "una caché nunca necesita invalidarse"

    anclado = _evaluar(
        VerificadorPorEvidencia(respaldadas), contenido=_contenido(*respaldadas)
    )
    con_invento = _evaluar(
        VerificadorPorEvidencia([*respaldadas, inventada]),
        contenido=_contenido(*respaldadas, inventada),
    )

    assert anclado["anclaje_fuente_score"] == 1.0
    assert con_invento["anclaje_fuente_score"] < anclado["anclaje_fuente_score"]


def test_el_verificador_recibe_la_evidencia_y_el_contenido_numerado():
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador, contenido=_contenido("uno", "dos"), perfil_destinatario="Principiante")

    sistema, humano = verificador.mensajes
    assert sistema.type == "system"
    assert "verificador de fidelidad" in sistema.content
    assert humano.type == "human"
    assert _TEXTO_0 in humano.content and _TEXTO_1 in humano.content
    assert "[Fuente: documento=doc-cache | chunk=doc-cache:0" in humano.content
    assert "Introducción: Vamos a ver qué es una caché." in humano.content
    assert "Item 1:" in humano.content and "Item 2:" in humano.content
    assert "Perfil del destinatario: Principiante" in humano.content


def test_sin_perfil_se_indica_que_no_esta_especificado():
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador)

    assert "Perfil del destinatario: no especificado" in verificador.mensajes[1].content


def test_busca_evidencia_por_cada_unidad_y_solo_en_el_documento():
    store = VectorStoreFake([*_EVIDENCIA, _DE_OTRO_DOCUMENTO])
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador, contenido=_contenido("uno", "dos"), store=store)

    assert len(store.llamadas) == 3  # la introducción y los dos items
    assert all(llamada["documento_id"] == _DOC for llamada in store.llamadas)
    assert all(llamada["top_k"] == fidelity_service.FRAGMENTOS_POR_UNIDAD for llamada in store.llamadas)
    assert "Texto de otro documento." not in verificador.mensajes[1].content


def test_la_evidencia_no_se_repite_aunque_varios_items_traigan_el_mismo_fragmento():
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador, contenido=_contenido("uno", "dos", "tres"))

    assert verificador.mensajes[1].content.count(_TEXTO_0) == 1


def test_la_evidencia_incluye_fragmentos_de_baja_similitud():
    """El verificador decide qué está respaldado: la búsqueda no descarta fragmentos por similitud."""
    poco_parecido = FragmentoRecuperado(
        chunk_id="doc-cache:9", documento_id=_DOC, texto="Fragmento poco parecido.", score=0.05, metadatos={}
    )
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador, store=VectorStoreFake([*_EVIDENCIA, poco_parecido]))

    assert "Fragmento poco parecido." in verificador.mensajes[1].content


def test_la_evidencia_no_se_recorta_con_el_limite_de_contexto_de_recuperacion(monkeypatch):
    """El límite de NM-06 acota el contexto de generación, no la evidencia de la verificación."""
    monkeypatch.setattr(settings, "RETRIEVAL_MAX_CONTEXT_TOKENS", 1)
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador)

    assert _TEXTO_0 in verificador.mensajes[1].content
    assert _TEXTO_1 in verificador.mensajes[1].content


def test_si_la_evidencia_supera_el_limite_se_conserva_lo_mas_relevante(monkeypatch):
    monkeypatch.setattr(fidelity_service, "MAX_TOKENS_EVIDENCIA", 40)  # entra un solo fragmento
    verificador = VerificadorFake(_respuesta([True]))

    _evaluar(verificador)

    assert _TEXTO_0 in verificador.mensajes[1].content  # el de mayor score
    assert _TEXTO_1 not in verificador.mensajes[1].content


def test_sin_fragmentos_igual_se_le_pide_al_verificador_que_juzgue():
    verificador = VerificadorFake(_respuesta([False]))

    resultado = _evaluar(verificador, store=VectorStoreFake([]))

    assert "(no se recuperaron fragmentos del documento)" in verificador.mensajes[1].content
    assert resultado["anclaje_fuente_score"] == 0.0


def test_un_score_bajo_el_umbral_se_registra_con_el_documento(caplog):
    """Criterio 5: el warning incluye el identificador del documento."""
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        _evaluar(VerificadorFake(_respuesta([True, False, False])), umbral=0.9)

    avisos = _avisos_de_fidelidad(caplog)
    assert len(avisos) == 1
    assert _DOC in avisos[0].getMessage()
    assert "0.33" in avisos[0].getMessage()


def test_un_score_sobre_el_umbral_no_registra_nada(caplog):
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        _evaluar(VerificadorFake(_respuesta([True, True])), umbral=0.9)

    assert not _avisos_de_fidelidad(caplog)


def test_usa_el_umbral_de_configuracion(monkeypatch, caplog):
    verificador = VerificadorFake(_respuesta([True, True, True, False]))  # score 0.75

    monkeypatch.setattr(settings, "FIDELITY_SCORE_THRESHOLD", 0.99)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        _evaluar(verificador)
    assert len(_avisos_de_fidelidad(caplog)) == 1

    caplog.clear()
    monkeypatch.setattr(settings, "FIDELITY_SCORE_THRESHOLD", 0.5)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        _evaluar(verificador)
    assert not _avisos_de_fidelidad(caplog)


@pytest.mark.parametrize(
    "respuesta",
    [
        [],
        {},
        {"afirmaciones": "no es lista", "claridad_pedagogica": "Alta", "observaciones": "texto"},
        {"afirmaciones": [{"respaldada": "si"}], "claridad_pedagogica": "Alta", "observaciones": "texto"},
        {"afirmaciones": [], "claridad_pedagogica": "Excelente", "observaciones": "texto"},
        {"afirmaciones": [], "claridad_pedagogica": "Alta", "observaciones": "   "},
        {"afirmaciones": [], "claridad_pedagogica": "Alta", "observaciones": 5},
    ],
)
def test_una_respuesta_con_forma_inesperada_levanta_error_tipado(respuesta):
    with pytest.raises(LLMProviderError):
        _evaluar(VerificadorFake(respuesta))


def test_propaga_el_timeout_del_verificador_como_error_tipado():
    with pytest.raises(LLMTimeoutError):
        _evaluar(VerificadorFake(LLMTimeoutError("sin respuesta")))


@pytest.mark.parametrize(
    "contenido",
    [
        {"titulo": "Vacío", "introduccion_contextualizada": "", "items": []},
        {"titulo": "Sin items", "introduccion_contextualizada": "Intro.", "items": "no es una lista"},
    ],
)
def test_contenido_que_no_se_puede_verificar_levanta_value_error(contenido):
    with pytest.raises(ValueError):
        _evaluar(VerificadorFake(_respuesta([True])), contenido=contenido)


def test_el_metodo_de_calculo_esta_documentado_en_el_modulo():
    """Criterio 3: el método de cálculo del score vive en el repo."""
    assert "Método de cálculo de `anclaje_fuente_score`" in fidelity_service.__doc__
