import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from components.file_uploader import render_file_uploader
from components.error_display import render_error
from components.loading_indicator import loading_indicator
from components.package_result import render_package_result
from components.sidebar import render_adaptation_options
from services.api_client import APIClientError, adapt_document, extract_document
from components.download_json import render_json_download
from utils.session_state import init_session_state


FRONTEND_DIR = Path(__file__).resolve().parent
load_dotenv(FRONTEND_DIR / ".env")
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost:8000/api/v1",
).rstrip("/")


def _timeout_from_environment(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        timeout = int(value)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un entero positivo.") from error
    if timeout <= 0:
        raise ValueError(f"{name} debe ser un entero positivo.")
    return timeout


API_TIMEOUT = (
    _timeout_from_environment("API_CONNECT_TIMEOUT_SECONDS", 5),
    _timeout_from_environment("API_READ_TIMEOUT_SECONDS", 180),
)

st.set_page_config(
    page_title="NuevaMente | Adaptación educativa",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_session_state()


def load_styles() -> None:
    stylesheet = FRONTEND_DIR / "assets" / "styles.css"
    if stylesheet.exists():
        st.markdown(
            f"<style>{stylesheet.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def run_adaptation(
    uploaded_file,
    title: str,
    options: dict[str, str],
) -> dict:
    extracted = extract_document(
        api_base_url=API_BASE_URL,
        file_name=uploaded_file.name,
        file_content=uploaded_file.getvalue(),
        content_type=uploaded_file.type,
        timeout=API_TIMEOUT,
    )
    content = extracted.get("text", "")
    if not content.strip():
        raise APIClientError("No se pudo extraer texto del documento.")

    payload = {
        "documento_titulo": title.strip(),
        "documento_contenido": content,
        **options,
    }
    pages = extracted.get("pages") or []
    if pages:
        payload["documento_paginas"] = pages
    return adapt_document(
        api_base_url=API_BASE_URL,
        payload=payload,
        timeout=API_TIMEOUT,
    )


load_styles()

supported_extensions = {".pdf", ".md", ".txt"}
source_document = st.session_state.get("source_document")
has_source_document = (
    source_document is not None
    and Path(source_document.name).suffix.lower() in supported_extensions
    and source_document.size > 0
)
options = render_adaptation_options(
    has_source_document=has_source_document,
)
st.session_state["loaded_document"] = source_document
st.session_state["selected_parameters"] = options.copy()

st.markdown(
    """
    <div class="topline"><span class="brand-mark">N</span><span>NUEVAMENTE</span>
    <span class="topline-rule"></span><span class="topline-caption">LABORATORIO DE APRENDIZAJE</span></div>
    <div class="page-heading"><div><p class="eyebrow">ESPACIO DE TRABAJO / ADAPTACIÓN</p>
    <h1>Del documento al aprendizaje.</h1>
    <p class="lede">Convierte material técnico en recursos educativos conectados a su fuente.</p></div>
    <div class="heading-index"><span>NM</span><strong>01</strong><small>GENERADOR</small></div></div>
    """,
    unsafe_allow_html=True,
)

uploaded_file = render_file_uploader()
file_extension = (
    Path(uploaded_file.name).suffix.lower() if uploaded_file else ""
)
valid_source_file = (
    uploaded_file is not None
    and file_extension in supported_extensions
    and uploaded_file.size > 0
)

if uploaded_file is not None:
    if file_extension not in supported_extensions:
        st.warning(
            "Formato no soportado. Sube un archivo PDF, "
            "Markdown (.md) o de texto (.txt)."
        )
    elif uploaded_file.size == 0:
        st.warning("El archivo está vacío. Sube un documento con contenido.")
    else:
        st.success(f"Documento cargado: {uploaded_file.name}")

with st.form("adaptation_form"):
    default_title = Path(uploaded_file.name).stem if uploaded_file else ""
    document_title = st.text_input(
        "Título del documento",
        value=default_title,
        placeholder="Ej. Introducción a redes en la nube",
        help="Este título identifica el material fuente en el contenido generado.",
    )
    submitted = st.form_submit_button(
        "Generar contenido",
        type="primary",
        icon=":material/auto_awesome:",
        disabled=not valid_source_file,
    )

if submitted:
    if uploaded_file is None:
        st.warning("Selecciona un documento antes de generar el material.")
    elif len(document_title.strip()) < 3:
        st.warning("El título debe tener al menos 3 caracteres.")
    else:
        st.session_state["is_loading"] = True
        try:
            with loading_indicator(
                "Extrayendo el documento y preparando el material..."
            ):
                result = run_adaptation(
                    uploaded_file,
                    document_title,
                    options,
                )

            if result.get("status") != "exito":
                error = result.get("error")
                if not isinstance(error, dict):
                    error = {
                        "mensaje": "No se pudo completar la adaptación."
                    }
                render_error(error)
            else:
                st.session_state["last_response"] = result
                st.session_state["document_title"] = document_title.strip()
                st.session_state["source_filename"] = uploaded_file.name
                st.success("El contenido educativo se generó correctamente.")

        except APIClientError as error:
            render_error(error.error)
        finally:
            st.session_state["is_loading"] = False

result = st.session_state.get("last_response")

st.divider()
st.subheader("Resultados")
if result and result.get("status") == "exito":
    with st.container():
        render_package_result(result)
        render_json_download(
            result,
            titulo_documento=st.session_state.get("document_title"),
            archivo_origen=st.session_state.get("source_filename"),
        )
else:
    st.caption("El contenido generado aparecerá aquí después de la adaptación.")

st.markdown(
    f'<div class="api-footnote"><span class="status-dot"></span> API · {API_BASE_URL}</div>',
    unsafe_allow_html=True,
)