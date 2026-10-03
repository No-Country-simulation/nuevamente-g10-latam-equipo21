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


def test_generation_extracts_then_adapts_and_shows_result(monkeypatch):
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
					"titulo": "Tutorial generado",
					"introduccion_contextualizada": "",
					"items": [],
				},
				"evaluacion_calidad": {},
				"almacenamiento_oci": {
					"status_upload": "error",
					"objeto_id": "mock-no-persistido",
				},
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
	assert any(title.value == "Tutorial generado" for title in app.title)
	assert any(metric.label == "Persistencia OCI" and metric.value == "No se persistió" for metric in app.metric)
	assert not any("mock-no-persistido" in caption.value for caption in app.caption)


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

	assert any("Servicio no disponible" in error.value for error in app.error)
	assert not app.button[0].disabled
	assert app.selectbox[0].value == "Principiante"
