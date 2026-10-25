import pytest

from app.services.prompt_builder import construir_mensajes_adaptacion
from app.services.prompt_builder import _instruccion_cantidad

_CONTEXTO_DE_PRUEBA = "Un índice acelera las búsquedas a costa de espacio en disco."

def _construir(**overrides):
    base = dict(
        documento_titulo="Índices en bases de datos",
        contexto_recuperado=_CONTEXTO_DE_PRUEBA,
        perfil_destinatario="Principiante",
        formato_salida="Flashcards",
        nicho_sector="General",
        nivel_detalle="Introductorio",
    )
    base.update(overrides)
    return construir_mensajes_adaptacion(**base)

def test_devuelve_un_mensaje_de_sistema_y_uno_humano():
    mensajes = _construir()
    assert len(mensajes) == 2
    assert mensajes[0].type == "system"
    assert mensajes[1].type == "human"

def test_incluye_siempre_el_contexto_recuperado_y_la_regla_de_grounding():
    mensajes = _construir()
    texto_completo = "\n".join(m.content for m in mensajes)
    assert _CONTEXTO_DE_PRUEBA in texto_completo
    assert "EXCLUSIVAMENTE" in texto_completo

def test_perfiles_distintos_producen_prompts_distintos():
    principiante = _construir(perfil_destinatario="Principiante")[1].content
    lider = _construir(perfil_destinatario="Lider_Tecnico_Arquitecto")[1].content
    assert principiante != lider

def test_formatos_distintos_producen_prompts_distintos_y_reflejan_la_forma_de_items():
    flashcards = _construir(formato_salida="Flashcards")[1].content
    tutorial = _construir(formato_salida="Tutorial")[1].content
    assert flashcards != tutorial
    assert "frente" in flashcards
    assert "paso_numero" in tutorial

def test_nicho_queda_reflejado_en_el_prompt():
    fintech = _construir(nicho_sector="Fintech")[1].content
    general = _construir(nicho_sector="General")[1].content
    assert fintech != general
    assert "financiero" in fintech

def test_nivel_detalle_altera_el_prompt_independientemente_del_perfil():
    # Con perfil fijo, cambiar nivel_detalle debe cambiar el prompt.
    intro_lider = _construir(
        perfil_destinatario="Lider_Tecnico_Arquitecto", nivel_detalle="Introductorio"
    )[1].content
    profundo_lider = _construir(
        perfil_destinatario="Lider_Tecnico_Arquitecto", nivel_detalle="Tecnico_Profundo"
    )[1].content
    assert intro_lider != profundo_lider

    # El mismo cambio de nivel_detalle, con OTRO perfil fijo, también debe variar el prompt:
    # confirma que el eje nivel_detalle es independiente del eje perfil_destinatario.
    intro_principiante = _construir(
        perfil_destinatario="Principiante", nivel_detalle="Introductorio"
    )[1].content
    profundo_principiante = _construir(
        perfil_destinatario="Principiante", nivel_detalle="Tecnico_Profundo"
    )[1].content
    assert intro_principiante != profundo_principiante

def test_valor_desconocido_en_un_eje_falla_explicitamente():
    with pytest.raises(KeyError):
        _construir(perfil_destinatario="Perfil_Inexistente")

def test_feedback_critico_agrega_contenido_anterior_y_mensaje_de_revision():
    feedback = (
        "El item 2 contiene una afirmación "
        "no respaldada por el documento."
    )

    contenido_anterior = (
        '{"titulo":"Versión anterior",'
        '"introduccion_contextualizada":"Contenido previo",'
        '"items":[]}'
    )

    mensajes = _construir(
        feedback_critico=feedback,
        contenido_anterior_serializado=contenido_anterior,
    )

    assert len(mensajes) == 3
    assert mensajes[2].type == "human"
    assert contenido_anterior in mensajes[2].content
    assert feedback in mensajes[2].content
    assert "versión completa corregida" in mensajes[2].content


def test_cantidad_respeta_el_minimo_con_contexto_corto():
    texto = _instruccion_cantidad("Quiz", "x" * 100)
    assert "entre 5 y 10 items" in texto


def test_cantidad_se_acota_al_maximo_con_contexto_largo():
    texto = _instruccion_cantidad("Tutorial", "x" * 20000)
    assert "entre 10 y 10 items" in texto


def test_cantidad_crece_con_el_largo_del_contexto():
    texto = _instruccion_cantidad("Resumen_Ejecutivo", "x" * 3936)
    assert "entre 8 y 12 items" in texto


def test_cantidad_usa_rango_por_defecto_si_el_formato_es_desconocido():
    texto = _instruccion_cantidad("Otro", "x" * 100)
    assert "entre 4 y 8 items" in texto


def test_el_prompt_incluye_la_instruccion_de_cantidad():
    mensajes = construir_mensajes_adaptacion(
        documento_titulo="Prueba",
        contexto_recuperado="x" * 3253,
        perfil_destinatario="Principiante",
        formato_salida="Tutorial",
        nicho_sector="General",
        nivel_detalle="Didactico",
    )
    assert "Cantidad de items: genera entre 7 y 10 items" in mensajes[1].content