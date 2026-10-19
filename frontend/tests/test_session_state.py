from pathlib import Path

from streamlit.testing.v1 import AppTest


FRONTEND_DIR = Path(__file__).resolve().parents[1]


def test_init_session_state_sets_defaults_and_preserves_existing_values():
    script = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from utils.session_state import init_session_state

init_session_state()
st.session_state["loaded_document"] = "lesson.md"
st.session_state["selected_parameters"] = {{"nivel_detalle": "Didactico"}}
st.session_state["last_response"] = {{"status": "exito"}}
st.session_state["is_loading"] = True
init_session_state()
"""
    app = AppTest.from_string(script, default_timeout=10).run()

    assert not app.exception
    assert app.session_state["loaded_document"] == "lesson.md"
    assert app.session_state["selected_parameters"] == {
        "nivel_detalle": "Didactico"
    }
    assert app.session_state["last_response"] == {"status": "exito"}
    assert app.session_state["is_loading"] is True
    assert app.session_state["source_filename"] is None
