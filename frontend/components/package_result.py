"""Visualización del paquete educativo generado."""

import streamlit as st


def render_flashcards(items: list[dict]) -> None:
    for number, item in enumerate(items, 1):
        with st.container(border=True):
            st.caption(f"FLASHCARD {number}")

            st.markdown("**Frente**")
            st.write(item["frente"])

            st.markdown("**Dorso**")
            st.write(item["dorso"])

            st.info(f"Pista didáctica: {item['pista_didactica']}")


def render_quiz(items: list[dict]) -> None:
    for number, item in enumerate(items, 1):
        with st.container(border=True):
            st.subheader(f"Pregunta {number}")
            st.write(item["pregunta"])

            for option in item["opciones"]:
                st.write(f"• {option}")

            with st.expander(
                "Ver respuesta y justificación",
                expanded=False,
            ):
                st.markdown("**Respuesta correcta**")
                st.write(item["respuesta_correcta"])

                st.markdown("**Justificación**")
                st.write(item["justificacion"])


def render_tutorial(items: list[dict]) -> None:
    for item in items:
        with st.container(border=True):
            st.subheader(
                f"Paso {item['paso_numero']} · {item['titulo_paso']}"
            )
            st.write(item["contenido"])

            if item.get("codigo_ejemplo"):
                st.code(item["codigo_ejemplo"], language=None)


def render_executive_summary(items: list[dict]) -> None:
    for item in items:
        with st.container(border=True):
            st.subheader(item["punto_clave"])

            st.markdown("**Descripción**")
            st.write(item["descripcion"])

            st.markdown("**Impacto de negocio**")
            st.write(item["impacto_negocio"])


def render_lesson_plan(items: list[dict]) -> None:
    for item in items:
        with st.container(border=True):
            st.subheader(item["seccion"])
            st.caption(
                f"Tiempo estimado: {item['tiempo_estimado_minutos']} min"
            )

            st.markdown("**Narración**")
            st.write(item["narracion"])

            st.markdown("**Notas visuales**")
            st.write(item.get("notas_visuales") or "Sin notas visuales.")


RENDERERS = {
    "Flashcards": render_flashcards,
    "Quiz": render_quiz,
    "Tutorial": render_tutorial,
    "Resumen_Ejecutivo": render_executive_summary,
    "Guion_Clase": render_lesson_plan,
}


def render_package_result(result: dict) -> None:
    if result.get("status") != "exito":
        return

    content = result.get("contenido_adaptado")
    metadata = result.get("metadatos")

    if not content or not metadata:
        st.warning("La respuesta no incluye el paquete educativo completo.")
        return

    st.divider()
    st.caption("PAQUETE EDUCATIVO GENERADO")
    st.header(content["titulo"])
    st.write(content["introduccion_contextualizada"])

    # El formato se toma del resultado generado, no de la selección actual.
    output_format = metadata["formato_generado"]
    st.caption(f"Formato: {output_format.replace('_', ' ')}")

    st.metric(
        "Tiempo estimado de estudio",
        f"{metadata['tiempo_estimado_estudio_minutos']} min",
    )

    st.markdown("**Conceptos clave**")
    for concept in metadata["conceptos_clave"]:
        st.write(f"• {concept}")

    renderer = RENDERERS.get(output_format)
    if renderer:
        renderer(content["items"])
    else:
        st.warning("El formato recibido no tiene una vista disponible.")

    st.subheader("Calidad del contenido")
    quality = result.get("evaluacion_calidad", {})

    score_column, clarity_column = st.columns(2)
    score = quality.get("anclaje_fuente_score")

    score_column.metric(
        "Anclaje a la fuente",
        f"{score:.2f}" if score is not None else "No disponible",
    )
    clarity_column.metric(
        "Claridad pedagógica",
        quality.get("claridad_pedagogica", "No disponible"),
    )

    st.markdown("**Observaciones**")
    st.write(quality.get("observaciones") or "Sin observaciones.")

    st.subheader("Almacenamiento OCI")
    storage = result.get("almacenamiento_oci", {})

    if storage.get("status_upload") == "completado":
        st.success("Contenido guardado en OCI.")
        st.text(f"Bucket: {storage['bucket']}")
        st.text(f"Objeto: {storage['objeto_id']}")
    elif storage.get("status_upload") == "error":
        st.warning(
            "El contenido fue generado correctamente, "
             "pero no se persistió en OCI."
        )
    else:
        st.info("No se recibió confirmación de almacenamiento en OCI.")