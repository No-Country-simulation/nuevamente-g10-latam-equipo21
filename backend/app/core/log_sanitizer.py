"""Sanitización de excepciones antes de escribirlas en logs.

Motivo: registrar `exc_info=exc` guarda el mensaje original y el traceback
completo. Si una dependencia (Gemini, OCI, etc.) incluye una credencial en el
mensaje de error, quedaría almacenada en los logs.

`error_sanitizado` devuelve una sola línea con: clase de la excepción, mensaje
con credenciales redactadas (y truncado) y las últimas líneas del traceback
(archivo:línea:función), sin valores de variables.

La redacción por expresiones regulares es de mejor esfuerzo: cubre los
formatos de credenciales más comunes, no garantiza cubrir cualquier formato.
"""

import re
import traceback

REDACTADO = "[REDACTADO]"

_PATRONES = [
    # Claves de API de Google (formato AIza...).
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), REDACTADO),
    # Cabeceras Authorization: Bearer xxx
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=\-]+"), f"Bearer {REDACTADO}"),
    # clave=valor / clave: valor (también en URLs: ?key=xxx)
    (
        re.compile(
            r"(?i)\b(api[_-]?key|key|token|secret|password|passphrase|authorization)"
            r"(\s*[=:]\s*)(\"?)[^\s,;&'\"]+"
        ),
        rf"\1\2\3{REDACTADO}",
    ),
    # Bloques de clave privada PEM
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        REDACTADO,
    ),
]


def sanitizar_texto(texto: str, max_len: int = 300) -> str:
    """Redacta credenciales conocidas y trunca el texto."""
    for patron, reemplazo in _PATRONES:
        texto = patron.sub(reemplazo, texto)
    if len(texto) > max_len:
        texto = texto[:max_len] + "…"
    return texto


def error_sanitizado(exc: BaseException, max_len: int = 300, frames: int = 3) -> str:
    """Resume una excepción para logs sin exponer secretos ni valores locales."""
    mensaje = sanitizar_texto(str(exc), max_len=max_len)
    ubicacion = " <- ".join(
        f"{f.filename.replace(chr(92), '/').split('/')[-1]}:{f.lineno}:{f.name}"
        for f in traceback.extract_tb(exc.__traceback__)[-frames:]
    )
    base = f"{type(exc).__name__}: {mensaje}"
    return f"{base} [{ubicacion}]" if ubicacion else base
