"""Inicialización y manejo del estado de sesión de Streamlit."""

import hashlib

import streamlit as st


def init_session_state() -> None:
    defaults = {
        "loaded_document": None,
        "selected_parameters": {},
        "last_response": None,
        "document_title": None,
        "is_loading": False,
        "source_filename": None,
        "quiz_signature": None,
        "quiz_answers": {},
        "quiz_confirmed_answers": {},
        "quiz_attempt": 0,
        "api_status": None,
        # NM-35: identidad del archivo actualmente cargado. Permite detectar
        # cuándo el usuario sube un archivo distinto, para invalidar el
        # resultado que había en pantalla (puede no corresponder al nuevo).
        "current_file_signature": None,
        # NM-35: parámetros con los que se generó el resultado MOSTRADO
        # actualmente. A diferencia de `selected_parameters` (que refleja la
        # selección en vivo de la barra lateral y puede cambiar sin invalidar
        # el resultado, ver NM-19), este valor solo se actualiza cuando una
        # generación termina con éxito.
        "applied_parameters": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def file_signature(uploaded_file) -> str | None:
    """Identidad estable de un archivo subido (NM-35).

    Combina nombre y hash del contenido: dos archivos con el mismo nombre
    y tamaño pero contenido distinto se consideran archivos distintos.
    """
    if uploaded_file is None:
        return None
    digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    return f"{uploaded_file.name}:{digest}"


def clear_result() -> None:
    """Limpia el resultado mostrado y su contexto (NM-35).

    Se invoca cuando el resultado en pantalla deja de corresponder a lo que
    el usuario ve: se cargó un archivo nuevo, o la generación más reciente
    falló. Nunca se invoca por cambiar un selector (eso rompería NM-19).
    """
    st.session_state["last_response"] = None
    st.session_state["document_title"] = None
    st.session_state["source_filename"] = None
    st.session_state["applied_parameters"] = None
