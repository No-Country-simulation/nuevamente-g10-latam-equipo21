import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from components.file_uploader import render_file_uploader
from components.result_view import render_result
from components.sidebar import render_adaptation_options
from services.api_client import APIClientError, adapt_document, extract_document


FRONTEND_DIR = Path(__file__).resolve().parent
load_dotenv(FRONTEND_DIR / ".env")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")

st.set_page_config(
	page_title="NuevaMente | Adaptación educativa",
	page_icon="N",
	layout="wide",
	initial_sidebar_state="expanded",
)


def load_styles() -> None:
	stylesheet = FRONTEND_DIR / "assets" / "styles.css"
	if stylesheet.exists():
		st.markdown(f"<style>{stylesheet.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def run_adaptation(uploaded_file, title: str, options: dict[str, str]) -> dict:
	extracted = extract_document(
		api_base_url=API_BASE_URL,
		file_name=uploaded_file.name,
		file_content=uploaded_file.getvalue(),
		content_type=uploaded_file.type,
	)
	content = extracted.get("text", "")
	if not content.strip():
		raise APIClientError("No se pudo extraer texto del documento.")

	payload = {
		"documento_titulo": title.strip(),
		"documento_contenido": content,
		**options,
	}
	return adapt_document(api_base_url=API_BASE_URL, payload=payload)


load_styles()
supported_extensions = {".pdf", ".md", ".txt"}
source_document = st.session_state.get("source_document")
has_source_document = (
	source_document is not None
	and Path(source_document.name).suffix.lower() in supported_extensions
	and source_document.size > 0
)
options = render_adaptation_options(has_source_document=has_source_document)

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
file_extension = Path(uploaded_file.name).suffix.lower() if uploaded_file else ""
valid_source_file = uploaded_file is not None and file_extension in supported_extensions and uploaded_file.size > 0
if uploaded_file is not None:
	if file_extension not in supported_extensions:
		st.warning("Formato no soportado. Sube un archivo PDF, Markdown (.md) o de texto (.txt).")
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
		try:
			with st.spinner("Extrayendo el documento y preparando el material..."):
				result = run_adaptation(uploaded_file, document_title, options)
			st.session_state["adaptation_result"] = result
			st.session_state["generation_id"] = st.session_state.get("generation_id", 0) + 1
			st.session_state["source_filename"] = uploaded_file.name
			st.session_state["generated_options"] = options.copy()
		except APIClientError as error:
			st.error(str(error))

result = st.session_state.get("adaptation_result")
generated_options = st.session_state.get("generated_options")
if result and generated_options != options:
	st.info("La configuración cambió. El resultado de abajo corresponde a la selección anterior.")

if result:
	render_result(result, st.session_state.get("source_filename", "Documento fuente"))
else:
	st.markdown(
		"""
		<div class="empty-state"><div class="empty-symbol">↗</div>
		<div><strong>Sin generación todavía</strong>
		<p>Selecciona un documento y genera el material educativo.</p></div>
		<span class="empty-step">EN ESPERA</span></div>
		""",
		unsafe_allow_html=True,
	)

st.markdown(
	f'<div class="api-footnote"><span class="status-dot"></span> API · {API_BASE_URL}</div>',
	unsafe_allow_html=True,
)
