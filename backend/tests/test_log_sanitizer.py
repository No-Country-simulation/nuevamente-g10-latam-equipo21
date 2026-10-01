from app.core.log_sanitizer import REDACTADO, error_sanitizado, sanitizar_texto

CLAVE_FALSA = "AIzaSyA1234567890abcdefghijklmnopqrstuv"


def test_redacta_clave_de_google():
    assert CLAVE_FALSA not in sanitizar_texto(f"request failed: {CLAVE_FALSA}")


def test_redacta_clave_en_query_string():
    texto = sanitizar_texto(f"GET https://x.googleapis.com/v1/models?key={CLAVE_FALSA}&pageSize=5")
    assert CLAVE_FALSA not in texto
    assert REDACTADO in texto


def test_redacta_bearer_token():
    texto = sanitizar_texto("Authorization: Bearer abc.def.ghi-123")
    assert "abc.def.ghi-123" not in texto


def test_redacta_pares_clave_valor():
    texto = sanitizar_texto("passphrase=hunter2 token: s3cr3t")
    assert "hunter2" not in texto
    assert "s3cr3t" not in texto


def test_no_toca_texto_normal():
    assert sanitizar_texto("API key not valid. Please pass a valid API key.") == (
        "API key not valid. Please pass a valid API key."
    )


def test_trunca_mensajes_largos():
    assert len(sanitizar_texto("x" * 1000, max_len=50)) <= 51


def _falla():
    raise RuntimeError(f"fallo con key={CLAVE_FALSA}")


def test_error_sanitizado_incluye_clase_y_ubicacion_sin_secreto():
    try:
        _falla()
    except RuntimeError as exc:
        resumen = error_sanitizado(exc)
    assert resumen.startswith("RuntimeError:")
    assert "_falla" in resumen
    assert CLAVE_FALSA not in resumen
