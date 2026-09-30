import pytest

from app.services.prompt_builder import construir_mensajes_adaptacion

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
