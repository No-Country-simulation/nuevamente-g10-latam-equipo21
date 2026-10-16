from typing import Any

import requests


class APIClientError(Exception):
	"""Error legible para fallas de conexión o respuestas de la API."""

	def __init__(
		self,
		message: str,
		*,
		error: dict[str, Any] | None = None,
	) -> None:
		super().__init__(message)
		self.error = error or {"mensaje": message}


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
		message = f"No se pudo conectar con la API en {api_base_url}. Verifica que FastAPI esté iniciado."
		raise APIClientError(
			message,
			error={"codigo": "ERROR_CONEXION", "mensaje": message},
		) from error
	except requests.ReadTimeout as error:
		message = (
			f"La API tardó más de {timeout[1]} segundos durante {operation}. "
			"Verifica los logs del backend para identificar la etapa demorada."
		)
		raise APIClientError(
			message,
			error={"codigo": "TIMEOUT_API", "mensaje": message},
		) from error
	except requests.Timeout as error:
		message = f"La solicitud de {operation} agotó el tiempo de espera. Intenta nuevamente."
		raise APIClientError(
			message,
			error={"codigo": "TIMEOUT_API", "mensaje": message},
		) from error

	try:
		data = response.json()
	except ValueError:
		data = None

	if not response.ok:
		error_data = data.get("error") if isinstance(data, dict) else None
		detail = data.get("detail") if isinstance(data, dict) else None
		error_data = error_data if isinstance(error_data, dict) else {}
		message = error_data.get("mensaje") or detail or "La API no pudo completar la solicitud."
		if isinstance(message, list):
			message = "; ".join(item.get("msg", "Entrada inválida") for item in message if isinstance(item, dict))
		error_payload = {
			**error_data,
			"mensaje": str(message),
		}
		raise APIClientError(str(message), error=error_payload)

	if data is None:
		raise APIClientError("La API respondió con un formato inesperado.")
	if isinstance(data, dict) and data.get("status") == "error":
		error_data = data.get("error")
		if isinstance(error_data, dict):
			message = error_data.get("mensaje") or "La API no pudo completar la solicitud."
			raise APIClientError(str(message), error=error_data)
	return data


def extract_document(
	*,
	api_base_url: str,
	file_name: str,
	file_content: bytes,
	content_type: str | None,
	timeout: tuple[int, int] = (5, 180),
) -> dict[str, Any]:
	return _request(
		api_base_url,
		"/documents/extract",
		operation="la extracción del documento",
		timeout=timeout,
		files={"file": (file_name, file_content, content_type or "application/octet-stream")},
	)


def adapt_document(
	*,
	api_base_url: str,
	payload: dict[str, Any],
	timeout: tuple[int, int] = (5, 180),
) -> dict[str, Any]:
	return _request(
		api_base_url,
		"/adaptar-contenido",
		operation="la adaptación del contenido",
		timeout=timeout,
		json=payload,
	)
