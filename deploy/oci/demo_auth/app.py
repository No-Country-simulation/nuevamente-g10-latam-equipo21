"""Acceso por sesión para la demo, usado por Traefik ForwardAuth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs

import bcrypt
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response


COOKIE_NAME = "__Host-nm_session"
CSRF_COOKIE_NAME = "__Host-nm_login_csrf"
SESSION_SECONDS = 12 * 60 * 60
CSRF_SECONDS = 30 * 60
MAX_FORM_BYTES = 4096
LOGIN_HTML = (Path(__file__).parent / "login.html").read_text(encoding="utf-8")
PUBLIC_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_app(*, users_file: Path, signing_key_file: Path, public_host: str) -> FastAPI:
    """Lee los secretos locales; el hash se recarga para invalidar sesiones al rotarlo."""
    if not public_host or "/" in public_host or ":" in public_host:
        raise ValueError("DEMO_AUTH_PUBLIC_HOST debe ser solo un nombre de dominio.")
    users_file.read_bytes()
    signing_key = _decode(signing_key_file.read_text(encoding="ascii").strip())
    if len(signing_key) < 32:
        raise ValueError("La clave de sesión debe tener al menos 32 bytes aleatorios.")

    service = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def password_hash(username: str) -> bytes | None:
        for line in users_file.read_bytes().splitlines():
            user, separator, digest = line.partition(b":")
            if separator and hmac.compare_digest(user, username.encode("utf-8")):
                return digest
        return None

    def valid_session(request: Request) -> bool:
        token = request.cookies.get(COOKIE_NAME, "")
        if len(token) > 2048:
            return False
        try:
            encoded, signature = token.split(".", 1)
            payload = _decode(encoded)
            expected = hmac.new(signing_key, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(_decode(signature), expected):
                return False
            username, issued, expires, password_fingerprint = payload.decode("utf-8").split("\t")
            now = int(time.time())
            if int(issued) > now or int(expires) <= now or int(expires) - int(issued) != SESSION_SECONDS:
                return False
            digest = password_hash(username)
            return bool(digest) and hmac.compare_digest(
                password_fingerprint, hashlib.sha256(digest).hexdigest()
            )
        except (ValueError, UnicodeError, OSError):
            return False

    def login_page(csrf_token: str, *, invalid: bool = False) -> HTMLResponse:
        error = (
            '<p class="error" role="alert">Usuario o contraseña incorrectos. Revisalos e intentá de nuevo.</p>'
            if invalid else ""
        )
        return HTMLResponse(
            LOGIN_HTML.replace("<!-- LOGIN_ERROR -->", error).replace(
                "<!-- LOGIN_CSRF -->",
                f'<input type="hidden" name="csrf_token" value="{csrf_token}">',
            ),
            headers=PUBLIC_HEADERS,
        )

    @service.get("/health", include_in_schema=False)
    def health() -> PlainTextResponse:
        return PlainTextResponse("ok", headers={"Cache-Control": "no-store"})

    @service.get("/acceso", include_in_schema=False)
    def access_page(request: Request) -> Response:
        if valid_session(request):
            return RedirectResponse("/", status_code=303, headers=PUBLIC_HEADERS)
        csrf_token = request.cookies.get(CSRF_COOKIE_NAME, "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", csrf_token):
            csrf_token = secrets.token_urlsafe(32)
        response = login_page(csrf_token)
        response.set_cookie(
            CSRF_COOKIE_NAME, csrf_token,
            max_age=CSRF_SECONDS, secure=True, httponly=True, samesite="strict", path="/",
        )
        return response

    @service.post("/acceso", include_in_schema=False)
    async def sign_in(request: Request) -> Response:
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > MAX_FORM_BYTES:
                return PlainTextResponse("Solicitud demasiado grande", status_code=413, headers=PUBLIC_HEADERS)
        try:
            fields = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=3)
            username = fields.get("username", [""])[0]
            password = fields.get("password", [""])[0]
        except (ValueError, UnicodeError):
            return PlainTextResponse("Solicitud no válida", status_code=400, headers=PUBLIC_HEADERS)

        csrf_token = request.cookies.get(CSRF_COOKIE_NAME, "")
        submitted_token = fields.get("csrf_token", [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", csrf_token) or not hmac.compare_digest(
            csrf_token, submitted_token
        ):
            return PlainTextResponse("Solicitud no válida. Recargá la página.", status_code=403, headers=PUBLIC_HEADERS)

        digest = password_hash(username)
        try:
            accepted = bool(digest) and bcrypt.checkpw(password.encode("utf-8"), digest)
        except ValueError:
            accepted = False
        if not accepted:
            return login_page(csrf_token, invalid=True)

        issued = int(time.time())
        fingerprint = hashlib.sha256(digest).hexdigest()
        payload = f"{username}\t{issued}\t{issued + SESSION_SECONDS}\t{fingerprint}".encode("utf-8")
        signature = hmac.new(signing_key, payload, hashlib.sha256).digest()
        response = RedirectResponse("/", status_code=303, headers=PUBLIC_HEADERS)
        response.set_cookie(
            COOKIE_NAME, f"{_encode(payload)}.{_encode(signature)}",
            max_age=SESSION_SECONDS, secure=True, httponly=True, samesite="lax", path="/",
        )
        response.delete_cookie(
            CSRF_COOKIE_NAME, secure=True, httponly=True, samesite="strict", path="/",
        )
        return response

    @service.get("/salir", include_in_schema=False)
    def sign_out() -> Response:
        response = RedirectResponse("/acceso", status_code=303, headers=PUBLIC_HEADERS)
        response.delete_cookie(COOKIE_NAME, secure=True, httponly=True, samesite="lax", path="/")
        return response

    @service.api_route("/verificar", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    def verify(request: Request) -> Response:
        if valid_session(request):
            return Response(status_code=204, headers={"Cache-Control": "no-store"})
        return RedirectResponse(f"https://{public_host}/acceso", status_code=303, headers=PUBLIC_HEADERS)

    return service


def create_from_env() -> FastAPI:
    return create_app(
        users_file=Path(os.environ.get("DEMO_AUTH_USERS_FILE", "/run/secrets/nuevamente-auth/users.htpasswd")),
        signing_key_file=Path(os.environ.get("DEMO_AUTH_SIGNING_KEY_FILE", "/run/secrets/nuevamente-auth/signing.key")),
        public_host=os.environ.get("DEMO_AUTH_PUBLIC_HOST", ""),
    )
