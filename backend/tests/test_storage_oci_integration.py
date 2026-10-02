"""Integración REAL contra el bucket OCI (NM-12 <-> NM-11).

NO corre por defecto ni en CI. Para ejecutarlo en tu máquina, con las credenciales
OCI ya cargadas en tu .env local:

    PowerShell:  $env:RUN_OCI_INTEGRATION = "1"; pytest tests/test_storage_oci_integration.py -v -s
    (después:    Remove-Item Env:RUN_OCI_INTEGRATION)

Se exige un opt-in explícito (y no solo mirar si hay credenciales) porque Settings
lee el .env: de otro modo cualquier `pytest` local subiría objetos al bucket.
El test sube un objeto de pocos KB con título identificable, lo lee de vuelta e
intenta borrarlo. Con la política IAM de mínimo privilegio (crear y leer, sin
eliminar) el borrado falla y el objeto permanece en el bucket; puede eliminarse
manualmente. Se reconoce por el nombre: contiene "test-integracion-nm12-".
"""

import os
import uuid
import warnings

import pytest

from app.core.config import settings
from app.schemas.input import InputSchema
from app.schemas.output import OutputSchema
from app.services.adaptacion_adapters import StorageOCIAdapter
from app.services.oci_storage_service import build_object_storage_client

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OCI_INTEGRATION") != "1" or not settings.OCI_NAMESPACE,
    reason="Integración OCI desactivada: definir RUN_OCI_INTEGRATION=1 y OCI_NAMESPACE.",
)


def test_adaptador_persiste_y_el_objeto_existe_en_el_bucket():
    titulo = f"test-integracion-nm12-{uuid.uuid4().hex[:8]}"
    payload = InputSchema(
        documento_titulo=titulo,
        documento_contenido="Contenido de prueba para la integración con OCI Object Storage. " * 5,
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Didactico",
    )
    paquete = {
        "metadatos": {
            "perfil_aplicado": "Principiante",
            "formato_generado": "Flashcards",
            "tiempo_estimado_estudio_minutos": 1,
            "conceptos_clave": ["prueba"],
            "prerrequisitos": [],
        },
        "contenido_adaptado": {
            "titulo": titulo,
            "introduccion_contextualizada": "Objeto de prueba; se borra al terminar.",
            "items": [{"frente": "f", "dorso": "d", "pista_didactica": "p"}],
        },
        "evaluacion_calidad": {
            "anclaje_fuente_score": 0.5,
            "claridad_pedagogica": "Media",
            "observaciones": "integración",
        },
    }

    resultado = StorageOCIAdapter().guardar(payload, paquete)

    client = build_object_storage_client(settings)
    try:
        assert resultado.status_upload == "completado", resultado
        assert resultado.bucket == settings.OCI_BUCKET_NAME
        assert titulo.replace("_", "-") in resultado.objeto_id

        leido = client.get_object(
            namespace_name=settings.OCI_NAMESPACE,
            bucket_name=resultado.bucket,
            object_name=resultado.objeto_id,
        )
        subido = OutputSchema.model_validate_json(leido.data.content)
        assert subido.contenido_adaptado.titulo == titulo
    finally:
        # Limpieza best-effort: si el objeto no llegó a existir, no hay nada que borrar.
        try:
            client.delete_object(
                namespace_name=settings.OCI_NAMESPACE,
                bucket_name=resultado.bucket,
                object_name=resultado.objeto_id,
            )
        except Exception as error:
            warnings.warn(
                f"No se pudo borrar el objeto de prueba '{resultado.objeto_id}' "
                f"({type(error).__name__}); puede permanecer en el bucket.",
                stacklevel=1,
            )