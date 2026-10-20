"""Inicialización del estado de sesión de Streamlit."""

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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
