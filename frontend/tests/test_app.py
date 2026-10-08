from pathlib import Path

import requests
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class FakeResponse:
	def __init__(self, payload: dict, *, ok: bool = True):
		self.payload = payload
		self.ok = ok

	def json(self) -> dict:
		return self.payload


def _app() -> AppTest:
	return AppTest.from_file(str(APP_PATH), default_timeout=10).run()


def test_initial_screen_has_contract_defaults_and_disabled_controls():
	app = _app()

	assert not app.exception
	assert any(element.value == "Resultados" for element in app.subheader)
	assert any(
		"aparecerá aquí después de la adaptación" in element.value
		for element in app.caption
	)
	assert app.session_state["last_response"] is None
	assert app.session_state["is_loading"] is False
	assert [selectbox.value for selectbox in app.selectbox] == [
		"Principiante",
		"Tutorial",
		"General",
		"Didactico",
	]
	assert [selectbox.label for selectbox in app.selectbox] == [
		"Perfil destinatario",
		"Formato de salida",
		"Nicho/Sector",
		"Nivel de detalle",
	]
	assert all(selectbox.disabled for selectbox in app.selectbox)
	assert app.button[0].disabled


def test_unsupported_file_is_rejected_without_enabling_generation():
	app = _app()
	app.file_uploader[0].set_value(("lesson.docx", b"content", "application/octet-stream"))
	app.run()

	assert any("Formato no soportado" in warning.value for warning in app.warning)
	assert all(selectbox.disabled for selectbox in app.selectbox)
	assert app.button[0].disabled


def test_supported_file_enables_controls_and_prefills_title():
	app = _app()
	app.file_uploader[0].set_value(("lesson.md", b"# Lesson", "text/markdown"))
	app.run()

	assert any("Documento cargado: lesson.md" in message.value for message in app.success)
	assert all(not selectbox.disabled for selectbox in app.selectbox)
	assert app.text_input[0].value == "lesson"
	assert not app.button[0].disabled
	assert app.session_state["loaded_document"].name == "lesson.md"
	assert app.session_state["selected_parameters"] == {
		"perfil_destinatario": "Principiante",
		"formato_salida": "Tutorial",
		"nicho_sector": "General",
		"nivel_detalle": "Didactico",
	}


def test_generation_extracts_then_adapts_and_shows_success_message(monkeypatch):
	calls = []
	responses = [
		FakeResponse({"text": "Texto fuente", "metadata": {}}),
		FakeResponse(
			{
				"status": "exito",
				"metadatos": {
					"formato_generado": "Tutorial",
					"tiempo_estimado_estudio_minutos": 10,
					"conceptos_clave": [],
				},
				"contenido_adaptado": {
					"titulo": "Resultado conservado",
					"introduccion_contextualizada": "Introducción",
					"items": [],
				},
				"evaluacion_calidad": {},
				"almacenamiento_oci": {},
			}
		),
	]

	def fake_request(method, url, **kwargs):
		calls.append((method, url, kwargs))
		return responses.pop(0)

	monkeypatch.setattr(requests, "request", fake_request)
	app = _app()
	app.file_uploader[0].set_value(("lesson.md", b"# Lesson", "text/markdown"))
	app.run()
	app.text_input[0].set_value("Lección adaptada")
	app.button[0].click()
	app.run()

	assert [call[1].rsplit("/", 1)[-1] for call in calls] == ["extract", "adaptar-contenido"]
	assert calls[0][2]["files"]["file"][:2] == ("lesson.md", b"# Lesson")
	assert calls[1][2]["json"] == {
		"documento_titulo": "Lección adaptada",
		"documento_contenido": "Texto fuente",
		"perfil_destinatario": "Principiante",
		"formato_salida": "Tutorial",
		"nicho_sector": "General",
		"nivel_detalle": "Didactico",
	}
	assert any("El contenido educativo se generó correctamente." in message.value for message in app.success)


def test_http_success_with_error_status_shows_only_adaptation_error(monkeypatch):
	responses = [
		FakeResponse({"text": "Texto fuente", "metadata": {}}),
		FakeResponse(
			{"status": "error", "error": {"codigo": "ERROR_TEST", "mensaje": "Servicio no disponible"}}
		),
	]

	monkeypatch.setattr(requests, "request", lambda *args, **kwargs: responses.pop(0))
	app = _app()
	app.file_uploader[0].set_value(("lesson.md", b"# Lesson", "text/markdown"))
	app.run()
	app.button[0].click()
	app.run()

	assert not app.exception
	assert not any(
		"El contenido educativo se generó correctamente." in message.value
		for message in app.success
	)
	assert app.session_state["last_response"] is None


def test_api_error_is_displayed_without_clearing_form_selections(monkeypatch):
	def fake_request(method, url, **kwargs):
		return FakeResponse(
			{"status": "error", "error": {"codigo": "ERROR_TEST", "mensaje": "Servicio no disponible"}},
			ok=False,
		)

	monkeypatch.setattr(requests, "request", fake_request)
	app = _app()
	app.file_uploader[0].set_value(("lesson.md", b"# Lesson", "text/markdown"))
	app.run()
	app.button[0].click()
	app.run()

	assert any(
		"ERROR_TEST: Servicio no disponible" in error.value
		for error in app.error
	)
	assert not app.button[0].disabled
	assert app.selectbox[0].value == "Principiante"


def test_selector_change_preserves_and_renders_last_response(monkeypatch):
	responses = [
		FakeResponse({"text": "Texto fuente", "metadata": {}}),
		FakeResponse(
			{
				"status": "exito",
				"metadatos": {
					"formato_generado": "Tutorial",
					"tiempo_estimado_estudio_minutos": 10,
					"conceptos_clave": [],
				},
				"contenido_adaptado": {
					"titulo": "Resultado conservado",
					"introduccion_contextualizada": "Introducción",
					"items": [],
				},
				"evaluacion_calidad": {},
				"almacenamiento_oci": {},
			}
		),
	]
	monkeypatch.setattr(
		requests,
		"request",
		lambda *args, **kwargs: responses.pop(0),
	)
	app = _app()
	app.file_uploader[0].set_value(("lesson.md", b"# Lesson", "text/markdown"))
	app.run()
	app.button[0].click()
	app.run()

	last_response = app.session_state["last_response"]
	assert last_response["contenido_adaptado"]["titulo"] == "Resultado conservado"
	assert app.session_state["is_loading"] is False

	app.selectbox[0].set_value("Desarrollador_Junior_SemiSenior")
	app.run()

	assert not app.exception
	assert app.session_state["last_response"] == last_response
	assert app.session_state["selected_parameters"]["perfil_destinatario"] == (
		"Desarrollador_Junior_SemiSenior"
	)
	assert any(
		header.value == "Resultado conservado"
		for header in app.header
	)


def test_generation_forwards_extracted_pages(monkeypatch):
	calls = []
	responses = [
		FakeResponse(
			{
				"text": "Texto fuente",
				"metadata": {},
				"pages": [
					{"page_number": 1, "text": "Pagina uno"},
					{"page_number": 2, "text": "Pagina dos"},
				],
			}
		),
		FakeResponse({"status": "exito", "mensaje": "Contenido listo"}),
	]

	def fake_request(method, url, **kwargs):
		calls.append((method, url, kwargs))
		return responses.pop(0)

	monkeypatch.setattr(requests, "request", fake_request)
	app = _app()
	app.file_uploader[0].set_value(("lesson.pdf", b"%PDF-1.4", "application/pdf"))
	app.run()
	app.button[0].click()
	app.run()

	assert calls[1][2]["json"]["documento_paginas"] == [
		{"page_number": 1, "text": "Pagina uno"},
		{"page_number": 2, "text": "Pagina dos"},
	]


def test_generation_without_pages_omits_documento_paginas(monkeypatch):
	calls = []
	responses = [
		FakeResponse({"text": "Texto fuente", "metadata": {}, "pages": []}),
		FakeResponse({"status": "exito", "mensaje": "Contenido listo"}),
	]

	def fake_request(method, url, **kwargs):
		calls.append((method, url, kwargs))
		return responses.pop(0)

	monkeypatch.setattr(requests, "request", fake_request)
	app = _app()
	app.file_uploader[0].set_value(("lesson.md", b"# Lesson", "text/markdown"))
	app.run()
	app.button[0].click()
	app.run()

	assert "documento_paginas" not in calls[1][2]["json"]
