import streamlit as st


def render_file_uploader():
	st.markdown('<p class="section-label">01 / MATERIAL FUENTE</p>', unsafe_allow_html=True)
	return st.file_uploader(
		"Documento fuente",
		accept_multiple_files=False,
		key="source_document",
		help="Formatos admitidos: PDF, Markdown y texto plano.",
		label_visibility="collapsed",
	)
