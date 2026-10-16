"""Componente reutilizable para mostrar errores en la interfaz."""

from collections.abc import Mapping
from typing import Any

import streamlit as st


def render_error(error: Mapping[str, Any]) -> None:
    code = error.get("codigo")
    message = error.get("mensaje")
    if not isinstance(message, str) or not message.strip():
        message = "No se pudo completar la solicitud."

    if isinstance(code, str) and code.strip():
        st.error(f"{code}: {message}")
    else:
        st.error(message)
