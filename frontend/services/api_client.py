from typing import Any

import requests


class APIClientError(Exception):
	"""Error legible para fallas de conexión o respuestas de la API."""


def _request(
	api_base_url: str,
	path: str,
	*,
	operation: str,
	timeout: tuple[int, int] = (5, 180),
	**kwargs: Any,
) -> Any:
	url = f"{api_base_url.rstrip('/')}/{path.lstrip('/')}"
	try:
		response = requests.request("POST", url, timeout=timeout, **kwargs)
	except requests.ConnectionError as error:
		raise APIClientError(f"No se pudo conectar con la API en {api_base_url}. Verifica que FastAPI esté iniciado.") from error
	except requests.ReadTimeout as error:
		raise APIClientError(
			f"La API tardó más de {timeout[1]} segundos durante {operation}. "
			"Verifica los logs del backend para identificar la etapa demorada."
		) from error
	except requests.Timeout as error:
		raise APIClientError(f"La solicitud de {operation} agotó el tiempo de espera. Intenta nuevamente.") from error

	try:
		data = response.json()
	except ValueError:
		data = None

	if not response.ok:
		error_data = data.get("error", {}) if isinstance(data, dict) else {}
		detail = data.get("detail") if isinstance(data, dict) else None
		message = error_data.get("mensaje") or detail or "La API no pudo completar la solicitud."
		if isinstance(message, list):
			message = "; ".join(item.get("msg", "Entrada inválida") for item in message if isinstance(item, dict))
		raise APIClientError(str(message))

	if data is None:
		raise APIClientError("La API respondió con un formato inesperado.")
	return data


def extract_document(
	*,
	api_base_url: str,
	file_name: str,
	file_content: bytes,
	content_type: str | None,
) -> dict[str, Any]:
	return _request(
		api_base_url,
		"/documents/extract",
		operation="la extracción del documento",
		files={"file": (file_name, file_content, content_type or "application/octet-stream")},
	)


def adapt_document(*, api_base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
	return _request(
		api_base_url,
		"/adaptar-contenido",
		operation="la adaptación del contenido",
		json=payload,
	)
