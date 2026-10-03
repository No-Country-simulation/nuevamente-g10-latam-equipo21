import html
import json

import streamlit as st

from components.flashcards_view import render_flashcards
from components.quiz_view import render_quiz
from components.tutorial_view import render_class_script, render_summary, render_tutorial


def _render_items(format_value: str, items: list[dict]) -> None:
    if format_value == "Flashcards":
        render_flashcards(items)
    elif format_value == "Quiz":
        render_quiz(items)
    elif format_value == "Tutorial":
        render_tutorial(items)
    elif format_value == "Resumen_Ejecutivo":
        render_summary(items)
    elif format_value == "Guion_Clase":
        render_class_script(items)
    else:
        st.json(items)


def render_result(result: dict, source_filename: str) -> None:
    if result.get("status") == "error":
        error = result.get("error", {})
        st.error(f"{error.get('codigo', 'ERROR')}: {error.get('mensaje', 'No se pudo generar el contenido.')}")
        return

    metadata = result.get("metadatos", {})
    content = result.get("contenido_adaptado", {})
    quality = result.get("evaluacion_calidad", {})
    storage = result.get("almacenamiento_oci", {})
    upload_status = storage.get("status_upload")
    if upload_status == "completado":
        storage_status = "Persistido"
    elif upload_status == "error":
        storage_status = "No se persistió"
    else:
        storage_status = "Estado no disponible"

    st.markdown('<p class="section-label result-label">03 / RECURSO GENERADO</p>', unsafe_allow_html=True)
    st.title(content.get("titulo", "Material adaptado"))
    st.caption(f"Fuente · {source_filename}")

    metrics = st.columns(4)
    metrics[0].metric("Estudio estimado", f"{metadata.get('tiempo_estimado_estudio_minutos', '—')} min")
    score = quality.get("anclaje_fuente_score")
    metrics[1].metric("Anclaje a fuente", f"{score:.0%}" if isinstance(score, (float, int)) else "—")
    metrics[2].metric("Claridad", quality.get("claridad_pedagogica", "—"))
    metrics[3].metric("Persistencia OCI", storage_status)

    if content.get("introduccion_contextualizada"):
        introduction = html.escape(str(content["introduccion_contextualizada"]))
        st.markdown(f'<div class="intro-copy">{introduction}</div>', unsafe_allow_html=True)

    tabs = st.tabs(["Contenido", "Calidad y fuente", "JSON"])
    with tabs[0]:
        _render_items(metadata.get("formato_generado", ""), content.get("items", []))
    with tabs[1]:
        concepts = metadata.get("conceptos_clave", [])
        prerequisites = metadata.get("prerrequisitos", [])
        left, right = st.columns(2)
        with left:
            st.markdown("#### Conceptos clave")
            st.write(" · ".join(concepts) if concepts else "Sin conceptos reportados.")
            st.markdown("#### Prerrequisitos")
            st.write(" · ".join(prerequisites) if prerequisites else "No se requieren prerrequisitos.")
        with right:
            st.markdown("#### Evaluación didáctica")
            st.write(quality.get("observaciones", "Sin observaciones."))
            st.markdown("#### Almacenamiento")
            st.caption(f"Bucket · {storage.get('bucket', 'No disponible')}")
            st.caption(f"Estado · {storage_status}")
            if upload_status == "completado":
                st.caption(f"Objeto · {storage.get('objeto_id', 'No disponible')}")
    with tabs[2]:
        st.json(result, expanded=True)

    st.download_button(
        "Descargar JSON",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name="nuevamente-contenido.json",
        mime="application/json",
        icon=":material/download:",
    )