"""Inicialización del estado de sesión de Streamlit."""

import streamlit as st


def init_session_state() -> None:
    defaults = {
        "loaded_document": None,
        "selected_parameters": {},
        "last_response": None,
        "is_loading": False,
        "source_filename": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
