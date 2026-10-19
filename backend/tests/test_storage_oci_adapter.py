"""Tests de StorageOCIAdapter (NM-12 <-> NM-11). Sin red: cliente OCI falso."""

import pytest

from app.core.config import settings
from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.adaptacion_adapters import (
    StorageOCIAdapter,
    _servicio_real,
    armar_respuesta_provisional,
)
from app.services.adaptacion_service import OBJETO_NO_PERSISTIDO, AdaptacionService
from app.services.oci_storage_service import (
    OCIStorageService,
    build_generated_object_name,
)

BUCKET_TEST = "bucket-test"

METADATOS = {
    "perfil_aplicado": "Principiante",
    "formato_generado": "Flashcards",
    "tiempo_estimado_estudio_minutos": 5,
    "conceptos_clave": ["VCN", "Subredes"],
    "prerrequisitos": [],
}
EVALUACION = {
    "anclaje_fuente_score": 0.9,
    "claridad_pedagogica": "Alta",
    "observaciones": "ok",
}
ITEMS_POR_FORMATO = {
    "Flashcards": [{"frente": "¿Qué es una VCN?", "dorso": "Una red privada.", "pista_didactica": "Piensa en tu LAN."}],
    "Quiz": [{
        "pregunta": "¿Qué es una VCN?",
        "opciones": ["Red privada", "Disco", "Usuario", "Región"],
        "respuesta_correcta": "Red privada",
        "justificacion": "Es una red virtual privada.",
    }],
    "Tutorial": [{"paso_numero": 1, "titulo_paso": "Crear VCN", "contenido": "Abrí la consola.", "codigo_ejemplo": None}],
    "Resumen_Ejecutivo": [{"punto_clave": "Aislamiento", "descripcion": "Red privada.", "impacto_negocio": "Menor riesgo."}],
    "Guion_Clase": [{"seccion": "Intro", "tiempo_estimado_minutos": 2, "narracion": "Hoy vemos VCN.", "notas_visuales": "Diagrama."}],
}


def hacer_paquete(formato: str = "Flashcards") -> dict:
    return {
        "metadatos": {**METADATOS, "formato_generado": formato},
        "contenido_adaptado": {
            "titulo": "Redes desde cero",
            "introduccion_contextualizada": "Intro.",
            "items": ITEMS_POR_FORMATO[formato],
        },
        "evaluacion_calidad": EVALUACION,
    }


def hacer_payload(formato: str = "Flashcards") -> InputSchema:
    return InputSchema(
        documento_titulo="Introducción a VCN en OCI",
        documento_contenido="La Virtual Cloud Network (VCN) es una red privada y personalizable. " * 5,
        perfil_destinatario="Principiante",
        formato_salida=formato,
        nicho_sector="General",
        nivel_detalle="Didactico",
    )


class FakeOCIClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def hacer_servicio(client: FakeOCIClient) -> OCIStorageService:
    return OCIStorageService(client, namespace="ns-test", bucket_name=BUCKET_TEST)


def test_camino_feliz_devuelve_completado_con_nombre_de_objeto():
    client = FakeOCIClient()
    adapter = StorageOCIAdapter(service_factory=lambda: hacer_servicio(client))
    payload = hacer_payload()

    resultado = adapter.guardar(payload, hacer_paquete())

    assert resultado.status_upload == "completado"
    assert resultado.bucket == BUCKET_TEST
    assert resultado.objeto_id == build_generated_object_name(payload)
    assert len(client.calls) == 1
    assert client.calls[0]["content_type"] == "application/json"
    assert client.calls[0]["object_name"] == resultado.objeto_id


def test_el_json_subido_es_un_output_schema_valido():
    client = FakeOCIClient()
    adapter = StorageOCIAdapter(service_factory=lambda: hacer_servicio(client))

    adapter.guardar(hacer_payload(), hacer_paquete())

    subido = OutputSchema.model_validate_json(client.calls[0]["put_object_body"])
    assert subido.status == "exito"
    assert subido.contenido_adaptado.titulo == "Redes desde cero"
    assert subido.metadatos.conceptos_clave == ["VCN", "Subredes"]


def test_si_put_object_falla_devuelve_error_con_el_nombre_del_objeto_y_no_lanza():
    client = FakeOCIClient(error=RuntimeError("fallo de red"))
    adapter = StorageOCIAdapter(service_factory=lambda: hacer_servicio(client))
    payload = hacer_payload()

    resultado = adapter.guardar(payload, hacer_paquete())

    assert resultado.status_upload == "error"
    assert resultado.objeto_id == build_generated_object_name(payload)


def test_si_la_fabrica_falla_guardar_lanza_y_persistir_devuelve_no_persistido():
    def fabrica_rota():
        raise ValueError("OCI_NAMESPACE debe configurarse")

    adapter = StorageOCIAdapter(service_factory=fabrica_rota)
    paquete = hacer_paquete()

    with pytest.raises(ValueError):
        adapter.guardar(hacer_payload(), paquete)

    # Mismo camino que en producción: AdaptacionService._persistir captura la excepción.
    servicio = AdaptacionService(None, None, None, None, storage=adapter)
    respuesta = armar_respuesta_provisional(paquete)
    resultado = servicio._persistir(
        hacer_payload(),
        respuesta.metadatos,
        respuesta.contenido_adaptado,
        respuesta.evaluacion_calidad,
    )

    assert resultado.status_upload == "error"
    assert resultado.objeto_id == OBJETO_NO_PERSISTIDO
    assert resultado.bucket == settings.OCI_BUCKET_NAME


def test_un_fallo_de_configuracion_no_queda_cacheado():
    client = FakeOCIClient()
    llamadas = {"n": 0}

    def fabrica_inestable():
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise ValueError("config incompleta")
        return hacer_servicio(client)

    adapter = StorageOCIAdapter(service_factory=fabrica_inestable)

    with pytest.raises(ValueError):
        adapter.guardar(hacer_payload(), hacer_paquete())
    resultado = adapter.guardar(hacer_payload(), hacer_paquete())

    assert resultado.status_upload == "completado"
    assert llamadas["n"] == 2


def test_el_servicio_se_construye_una_sola_vez_si_funciona():
    client = FakeOCIClient()
    llamadas = {"n": 0}

    def fabrica():
        llamadas["n"] += 1
        return hacer_servicio(client)

    adapter = StorageOCIAdapter(service_factory=fabrica)
    adapter.guardar(hacer_payload(), hacer_paquete())
    adapter.guardar(hacer_payload(), hacer_paquete())

    assert llamadas["n"] == 1
    assert len(client.calls) == 2


@pytest.mark.parametrize("formato", list(ITEMS_POR_FORMATO))
def test_la_reconstruccion_del_paquete_no_altera_el_contenido(formato):
    """Los items son una Union sin discriminador: el ida y vuelta dict -> schema -> dict
    no debe cambiar el tipo ni los valores de ningún item."""
    paquete = hacer_paquete(formato)

    respuesta = armar_respuesta_provisional(paquete)

    assert respuesta.contenido_adaptado.model_dump(mode="json") == paquete["contenido_adaptado"]
    assert respuesta.metadatos.model_dump(mode="json") == paquete["metadatos"]
    assert respuesta.evaluacion_calidad.model_dump(mode="json") == paquete["evaluacion_calidad"]
    assert respuesta.almacenamiento_oci.status_upload == "error"
    assert respuesta.almacenamiento_oci.objeto_id == OBJETO_NO_PERSISTIDO


def test_servicio_real_usa_el_adaptador_de_oci():
    _servicio_real.cache_clear()
    try:
        servicio = _servicio_real()
        assert isinstance(servicio._storage, StorageOCIAdapter)
    finally:
        _servicio_real.cache_clear()
