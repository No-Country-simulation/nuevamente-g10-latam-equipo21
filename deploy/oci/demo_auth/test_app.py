"""Pruebas del acceso web sin usar las credenciales de la demo."""

import base64
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient

from app import COOKIE_NAME, create_app


@pytest.fixture
def access(tmp_path: Path):
    users = tmp_path / "users.htpasswd"
    key = tmp_path / "signing.key"
    users.write_bytes(b"evaluador:" + bcrypt.hashpw(b"clave-prueba", bcrypt.gensalt(rounds=4)) + b"\n")
    key.write_text(base64.urlsafe_b64encode(b"a" * 32).decode("ascii"), encoding="ascii")
    return TestClient(
        create_app(users_file=users, signing_key_file=key, public_host="demo.example.com"),
        base_url="https://demo.example.com",
    ), users


def test_pagina_y_verificacion_sin_sesion(access):
    client, _ = access
    page = client.get("/acceso")
    assert page.status_code == 200
    assert '<form action="/acceso" method="post">' in page.text
    assert 'autocomplete="current-password"' in page.text
    assert page.headers["cache-control"] == "no-store"

    blocked = client.get("/verificar", follow_redirects=False)
    assert blocked.status_code == 303
    assert blocked.headers["location"] == "https://demo.example.com/acceso"
    assert "www-authenticate" not in blocked.headers


def test_login_sesion_y_salida(access):
    client, _ = access
    wrong = client.post("/acceso", data={"username": "evaluador", "password": "incorrecta"})
    assert wrong.status_code == 200
    assert "Usuario o contraseña incorrectos" in wrong.text
    assert COOKIE_NAME not in client.cookies

    response = client.post(
        "/acceso", data={"username": "evaluador", "password": "clave-prueba"},
        headers={"Origin": "https://demo.example.com"}, follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Domain=" not in cookie
    assert client.get("/verificar").status_code == 204

    logout = client.get("/salir", follow_redirects=False)
    assert logout.status_code == 303
    assert client.get("/verificar", follow_redirects=False).status_code == 303


def test_rotar_contrasena_invalida_sesion_anterior(access):
    client, users = access
    client.post("/acceso", data={"username": "evaluador", "password": "clave-prueba"}, follow_redirects=False)
    assert client.get("/verificar").status_code == 204
    users.write_bytes(b"evaluador:" + bcrypt.hashpw(b"clave-nueva", bcrypt.gensalt(rounds=4)) + b"\n")
    assert client.get("/verificar", follow_redirects=False).status_code == 303


def test_cookie_alterada_y_formulario_externo_no_conceden_acceso(access):
    client, _ = access
    denied = client.post(
        "/acceso", data={"username": "evaluador", "password": "clave-prueba"},
        headers={"Origin": "https://otro.example.com"},
    )
    assert denied.status_code == 403
    client.cookies.set(COOKIE_NAME, "falsificada.falsificada")
    assert client.get("/verificar", follow_redirects=False).status_code == 303


def test_formulario_excesivo_se_rechaza(access):
    client, _ = access
    response = client.post("/acceso", content=b"password=" + b"x" * 5000)
    assert response.status_code == 413
