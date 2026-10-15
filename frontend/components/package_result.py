"""Visualización del paquete educativo generado."""

import hashlib
import json

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
    quiz_signature = hashlib.sha256(
        json.dumps(items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("quiz_signature") != quiz_signature:
        st.session_state["quiz_signature"] = quiz_signature
        st.session_state["quiz_answers"] = {}
        st.session_state["quiz_attempt"] = 0

    answers = st.session_state.setdefault("quiz_answers", {})
    attempt = st.session_state.setdefault("quiz_attempt", 0)

    for number, item in enumerate(items, 1):
        with st.container(border=True):
            st.subheader(f"Pregunta {number}")
            st.write(item["pregunta"])

            options = item["opciones"]
            answer_key = f"quiz_answer_{quiz_signature}_{attempt}_{number}"
            previous_answer = answers.get(str(number))
            selected_index = (
                options.index(previous_answer) if previous_answer in options else None
            )
            selected_option = st.radio(
                "Selecciona una opción",
                options,
                index=selected_index,
                key=answer_key,
            )

            if selected_option is not None:
                answers[str(number)] = selected_option
                if selected_option == item["respuesta_correcta"]:
                    st.success("¡Correcto!")
                else:
                    st.error(
                        f"Incorrecto. La respuesta correcta es: {item['respuesta_correcta']}"
                    )
                st.info(f"Justificación: {item['justificacion']}")

    if items and len(answers) == len(items):
        correct_answers = sum(
            answers[str(number)] == item["respuesta_correcta"]
            for number, item in enumerate(items, 1)
        )
        score = round(correct_answers / len(items) * 100)
        score_column, correct_column = st.columns(2)
        score_column.metric("Puntaje final", f"{score}%")
        correct_column.metric("Aciertos", f"{correct_answers} de {len(items)}")

        if st.button("Reintentar", key=f"quiz_retry_{quiz_signature}"):
            answers.clear()
            st.session_state["quiz_attempt"] = attempt + 1
            st.rerun()


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