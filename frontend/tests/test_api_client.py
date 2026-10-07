import requests
import pytest

from services.api_client import APIClientError, adapt_document, extract_document


class FakeResponse:
	def __init__(self, payload: dict, *, ok: bool = True):
		self.payload = payload
		self.ok = ok

	def json(self) -> dict:
		return self.payload


def test_extract_document_posts_multipart_file(monkeypatch):
	observed = {}

	def fake_request(method, url, **kwargs):
		observed.update(method=method, url=url, kwargs=kwargs)
		return FakeResponse({"text": "Contenido", "metadata": {}})

	monkeypatch.setattr(requests, "request", fake_request)
	result = extract_document(
		api_base_url="http://api.test/api/v1/",
		file_name="source.md",
		file_content=b"# Source",
		content_type="text/markdown",
	)

	assert result["text"] == "Contenido"
	assert observed["method"] == "POST"
	assert observed["url"] == "http://api.test/api/v1/documents/extract"
	assert observed["kwargs"]["files"]["file"] == ("source.md", b"# Source", "text/markdown")


def test_api_client_uses_configured_timeout(monkeypatch):
	observed = {}

	def fake_request(method, url, **kwargs):
		observed.update(kwargs)
		return FakeResponse({"text": "Contenido", "metadata": {}})

	monkeypatch.setattr(requests, "request", fake_request)
	extract_document(
		api_base_url="http://api.test/api/v1",
		file_name="source.md",
		file_content=b"# Source",
		content_type="text/markdown",
		timeout=(2, 45),
	)

	assert observed["timeout"] == (2, 45)


def test_adapt_document_posts_contract_payload(monkeypatch):
	observed = {}
	payload = {"documento_titulo": "Fuente", "documento_contenido": "Texto"}

	def fake_request(method, url, **kwargs):
		observed.update(method=method, url=url, kwargs=kwargs)
		return FakeResponse(
			{
				"status": "exito",
				"almacenamiento_oci": {
					"status_upload": "error",
					"objeto_id": "mock-no-persistido",
				},
			}
		)

	monkeypatch.setattr(requests, "request", fake_request)
	result = adapt_document(api_base_url="http://api.test/api/v1", payload=payload)

	assert result["status"] == "exito"
	assert result["almacenamiento_oci"]["status_upload"] == "error"
	assert observed["url"] == "http://api.test/api/v1/adaptar-contenido"
	assert observed["kwargs"]["json"] == payload


def test_http_contract_error_surfaces_error_message(monkeypatch):
	monkeypatch.setattr(
		requests,
		"request",
		lambda *args, **kwargs: FakeResponse(
			{"status": "error", "error": {"codigo": "INVALIDO", "mensaje": "Documento inválido"}},
			ok=False,
		),
	)

	with pytest.raises(APIClientError, match="Documento inválido"):
		extract_document(
			api_base_url="http://api.test/api/v1",
			file_name="source.md",
			file_content=b"texto",
			content_type="text/markdown",
		)


def test_connection_error_is_translated_to_api_client_error(monkeypatch):
	def fail_request(*args, **kwargs):
		raise requests.ConnectionError("offline")

	monkeypatch.setattr(requests, "request", fail_request)

	with pytest.raises(APIClientError, match="No se pudo conectar"):
		adapt_document(api_base_url="http://api.test/api/v1", payload={})


def test_extract_read_timeout_identifies_document_extraction(monkeypatch):
	monkeypatch.setattr(
		requests,
		"request",
		lambda *args, **kwargs: (_ for _ in ()).throw(requests.ReadTimeout("slow")),
	)

	with pytest.raises(APIClientError, match="180 segundos durante la extracción del documento"):
		extract_document(
			api_base_url="http://api.test/api/v1",
			file_name="source.pdf",
			file_content=b"pdf",
			content_type="application/pdf",
		)


def test_adaptation_read_timeout_identifies_content_adaptation(monkeypatch):
	monkeypatch.setattr(
		requests,
		"request",
		lambda *args, **kwargs: (_ for _ in ()).throw(requests.ReadTimeout("slow")),
	)

	with pytest.raises(APIClientError, match="180 segundos durante la adaptación del contenido"):
		adapt_document(api_base_url="http://api.test/api/v1", payload={})
