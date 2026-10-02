"""Identificador de petición (NM-12): contextvar + middleware ASGI."""

import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()

def request_id_de(request) -> str:
    """Request ID para handlers que corren fuera del middleware (p. ej. el de 500)."""
    return getattr(request.state, "request_id", None) or get_request_id()


class RequestIdMiddleware:
    """Asigna un id por petición (o reutiliza el X-Request-ID entrante) y lo
    devuelve en el header de la respuesta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.lower().encode())
        rid = incoming.decode()[:64] if incoming else uuid.uuid4().hex
        token = _request_id.set(rid)
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER.lower().encode(), rid.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            _request_id.reset(token)
