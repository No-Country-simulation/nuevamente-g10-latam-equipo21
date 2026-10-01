"""Tests de NM-10 (metadatos de aprendizaje). Usan un LLM falso: no llaman a Gemini."""

import pytest

from app.schemas.content import FlashcardItem, GuionItem, QuizItem, ResumenItem, TutorialItem
from app.schemas.enums import FormatoSalida, PerfilDestinatario
from app.schemas.output import ContenidoAdaptadoSchema
from app.services.llm_provider import LLMProviderError
from app.services.metadata_service import (
    MetadatosInsuficientesError,
    MetadatosLLM,
    PrerrequisitoLLM,
    estimar_tiempo_estudio_minutos,
    generar_metadatos_aprendizaje,
)

DOCUMENTO = (
    "La Virtual Cloud Network (VCN) es una red privada y personalizable configurada en Oracle "
    "Cloud Infrastructure. Una VCN se divide en subredes. El Internet Gateway permite el acceso "
    "desde y hacia Internet. Las Security Lists controlan el tráfico de cada subred. "
    "Se asume que el lector conoce direccionamiento IP y la notación CIDR."
)


class LLMFalso:
    """Devuelve respuestas preparadas, una por llamada."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = 0

    def generate_structured(self, messages, schema):
        self.llamadas += 1
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _llm_ok():
    return MetadatosLLM(
        conceptos_clave=["VCN", "Subredes", "Internet Gateway", "Security Lists"],
        prerrequisitos=[
            PrerrequisitoLLM(
                concepto="Direccionamiento IP",
                cita_documento="el lector conoce direccionamiento IP y la notación CIDR",
            )
        ],
    )


def _contenido(formato: str) -> ContenidoAdaptadoSchema:
    items = {
        "Flashcards": [FlashcardItem(frente="¿Qué es una VCN?", dorso="Una red privada.", pista_didactica="Piensa en tu casa.")],
        "Quiz": [QuizItem(pregunta="¿Qué es una VCN?", opciones=["a", "b", "c", "d"], respuesta_correcta="a", justificacion="Es una red privada.")],
        "Tutorial": [TutorialItem(paso_numero=1, titulo_paso="Crear la VCN", contenido="Abre la consola y crea una VCN.", codigo_ejemplo=None)],
        "Resumen_Ejecutivo": [ResumenItem(punto_clave="VCN", descripcion="Red privada en la nube.", impacto_negocio="Aísla los sistemas.")],
        "Guion_Clase": [GuionItem(seccion="Intro", tiempo_estimado_minutos=2, narracion="Hoy vemos las VCN.", notas_visuales="Diagrama de red.")],
    }[formato]
    return ContenidoAdaptadoSchema(titulo="Redes en la nube", introduccion_contextualizada="Una introducción breve.", items=items)


def _generar(llm, formato="Flashcards", perfil="Principiante", documento=DOCUMENTO):
    return generar_metadatos_aprendizaje(
        documento_contenido=documento,
        contenido_adaptado=_contenido(formato),
        perfil_destinatario=perfil,
        formato_salida=formato,
        llm_provider=llm,
    )


@pytest.mark.parametrize("formato", ["Tutorial", "Flashcards", "Quiz", "Resumen_Ejecutivo", "Guion_Clase"])
def test_metadatos_para_los_cinco_formatos(formato):
    meta = _generar(LLMFalso(_llm_ok()), formato=formato)
    assert meta.formato_generado == FormatoSalida(formato)
    assert isinstance(meta.tiempo_estimado_estudio_minutos, int)
    assert meta.tiempo_estimado_estudio_minutos >= 1
    assert 3 <= len(meta.conceptos_clave) <= 8


def test_perfil_y_formato_se_copian_de_la_solicitud():
    meta = _generar(LLMFalso(_llm_ok()), formato="Quiz", perfil="Gestor_Ejecutivo_No_Tecnico")
    assert meta.perfil_aplicado == PerfilDestinatario("Gestor_Ejecutivo_No_Tecnico")
    assert meta.formato_generado == FormatoSalida.QUIZ


def test_descarta_conceptos_que_no_estan_en_el_documento():
    llm = LLMFalso(
        MetadatosLLM(
            conceptos_clave=["VCN", "Kubernetes", "Subredes", "Blockchain", "Security Lists"],
            prerrequisitos=[],
        )
    )
    meta = _generar(llm)
    assert meta.conceptos_clave == ["VCN", "Subredes", "Security Lists"]


def test_comparacion_ignora_mayusculas_acentos_y_plural():
    llm = LLMFalso(
        MetadatosLLM(conceptos_clave=["vcn", "SUBRED", "trafico", "internet gateway"], prerrequisitos=[])
    )
    meta = _generar(llm)
    assert len(meta.conceptos_clave) == 4


def test_no_repite_conceptos():
    llm = LLMFalso(MetadatosLLM(conceptos_clave=["VCN", "vcn", "Subredes", "Internet Gateway"], prerrequisitos=[]))
    assert _generar(llm).conceptos_clave == ["VCN", "Subredes", "Internet Gateway"]


def test_limita_a_ocho_conceptos():
    documento = " ".join(f"termino{i} explicacion" for i in range(12))
    llm = LLMFalso(MetadatosLLM(conceptos_clave=[f"termino{i}" for i in range(12)], prerrequisitos=[]))
    meta = _generar(llm, documento=documento)
    assert len(meta.conceptos_clave) == 8


def test_reintenta_una_vez_si_quedan_menos_de_tres():
    llm = LLMFalso(
        MetadatosLLM(conceptos_clave=["VCN", "Kubernetes", "Docker"], prerrequisitos=[]),
        _llm_ok(),
    )
    meta = _generar(llm)
    assert llm.llamadas == 2
    assert len(meta.conceptos_clave) == 4


def test_falla_si_tras_los_intentos_no_hay_tres_conceptos_verificables():
    malo = MetadatosLLM(conceptos_clave=["VCN", "Kubernetes", "Docker"], prerrequisitos=[])
    llm = LLMFalso(malo, malo)
    with pytest.raises(MetadatosInsuficientesError):
        _generar(llm)
    assert llm.llamadas == 2


def test_prerrequisito_con_cita_real_se_conserva():
    meta = _generar(LLMFalso(_llm_ok()))
    assert meta.prerrequisitos == ["Direccionamiento IP"]


def test_prerrequisito_con_cita_inventada_se_descarta():
    llm = LLMFalso(
        MetadatosLLM(
            conceptos_clave=["VCN", "Subredes", "Internet Gateway"],
            prerrequisitos=[
                PrerrequisitoLLM(concepto="Linux", cita_documento="el lector domina administración de Linux")
            ],
        )
    )
    assert _generar(llm).prerrequisitos == []


def test_sin_prerrequisitos_devuelve_lista_vacia():
    llm = LLMFalso(MetadatosLLM(conceptos_clave=["VCN", "Subredes", "Internet Gateway"], prerrequisitos=[]))
    assert _generar(llm).prerrequisitos == []


def test_tiempo_es_entero_positivo_y_crece_con_el_volumen():
    corto = _contenido("Resumen_Ejecutivo")
    largo = ContenidoAdaptadoSchema(
        titulo="t",
        introduccion_contextualizada="palabra " * 1000,
        items=corto.items,
    )
    t_corto = estimar_tiempo_estudio_minutos(corto, "Resumen_Ejecutivo")
    t_largo = estimar_tiempo_estudio_minutos(largo, "Resumen_Ejecutivo")
    assert t_corto == 1
    assert t_largo > t_corto


def test_quiz_lleva_mas_tiempo_que_resumen_con_el_mismo_texto():
    contenido = ContenidoAdaptadoSchema(
        titulo="t", introduccion_contextualizada="palabra " * 600, items=_contenido("Quiz").items
    )
    assert estimar_tiempo_estudio_minutos(contenido, "Quiz") > estimar_tiempo_estudio_minutos(
        contenido, "Resumen_Ejecutivo"
    )


def test_error_del_proveedor_no_se_traduce():
    with pytest.raises(LLMProviderError):
        _generar(LLMFalso(LLMProviderError("boom")))

def test_adaptador_real_delega_con_los_datos_del_payload():
    from types import SimpleNamespace

    from app.services.adaptacion_adapters import MetadatosRealAdapter

    recibido = {}

    def generar_falso(**kwargs):
        recibido.update(kwargs)
        return "META"

    payload = SimpleNamespace(
        documento_contenido=DOCUMENTO,
        perfil_destinatario=PerfilDestinatario("Principiante"),
        formato_salida=FormatoSalida("Flashcards"),
    )
    contenido = _contenido("Flashcards")
    llm = object()

    resultado = MetadatosRealAdapter(llm_provider=llm, generar=generar_falso).generar(payload, contenido)

    assert resultado == "META"
    assert recibido["documento_contenido"] == DOCUMENTO
    assert recibido["contenido_adaptado"] is contenido
    assert recibido["llm_provider"] is llm
    