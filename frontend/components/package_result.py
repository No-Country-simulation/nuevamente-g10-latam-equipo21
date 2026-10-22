"""Visualización del paquete educativo generado."""

import hashlib
import json
import re

import streamlit as st


def _correct_option_index(options: list[str], correct_answer: str) -> int | None:
    """Resolve a correct answer returned as text or as an option letter."""
    if correct_answer in options:
        return options.index(correct_answer)

    match = re.match(r"^\s*([A-Za-z])(?:\s*[).:\-]|\s*$)", correct_answer)
    if match:
        option_index = ord(match.group(1).upper()) - ord("A")
        if 0 <= option_index < len(options):
            return option_index

    return None


def _is_correct_option(
    options: list[str], selected_option: str, correct_answer: str
) -> bool:
    correct_index = _correct_option_index(options, correct_answer)
    return options.index(selected_option) == correct_index


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
        st.session_state["quiz_confirmed_answers"] = {}
        st.session_state["quiz_attempt"] = 0

    answers = st.session_state.setdefault("quiz_answers", {})
    confirmed_answers = st.session_state.setdefault("quiz_confirmed_answers", {})
    attempt = st.session_state.setdefault("quiz_attempt", 0)

    for number, item in enumerate(items, 1):
        with st.container(border=True):
            st.subheader(f"Pregunta {number}")
            st.write(item["pregunta"])

            options = item["opciones"]
            answer_key = f"quiz_answer_{quiz_signature}_{attempt}_{number}"
            confirm_key = f"quiz_confirm_{quiz_signature}_{attempt}_{number}"
            question_number = str(number)
            confirmed_choice = confirmed_answers.get(question_number)
            current_choice = answers.get(question_number, confirmed_choice)
            selected_index = (
                options.index(current_choice) if current_choice in options else None
            )

            is_locked = question_number in confirmed_answers
            selected_option = st.radio(
                "Selecciona una opción",
                options,
                index=selected_index,
                key=answer_key,
                disabled=is_locked,
            )

            if not is_locked and selected_option is not None:
                answers[question_number] = selected_option

            if is_locked and confirmed_choice is not None:
                correct_index = _correct_option_index(
                    options, item["respuesta_correcta"]
                )
                if _is_correct_option(
                    options, confirmed_choice, item["respuesta_correcta"]
                ):
                    st.success("¡Correcto!")
                else:
                    correct_display = (
                        options[correct_index]
                        if correct_index is not None
                        else item["respuesta_correcta"]
                    )
                    st.error(
                        f"Incorrecto. La respuesta correcta es: {correct_display}"
                    )
                st.info(f"Justificación: {item['justificacion']}")

            if not is_locked and question_number in answers:
                if st.button("Confirmar respuesta", key=confirm_key):
                    confirmed_answers[question_number] = answers[question_number]
                    answers.pop(question_number, None)
                    st.rerun()

    if items and len(confirmed_answers) == len(items):
        correct_answers = sum(
            _is_correct_option(
                item["opciones"],
                confirmed_answers[str(number)],
                item["respuesta_correcta"],
            )
            for number, item in enumerate(items, 1)
        )
        score = round(correct_answers / len(items) * 100)
        score_column, correct_column = st.columns(2)
        score_column.metric("Puntaje final", f"{score}%")
        correct_column.metric("Aciertos", f"{correct_answers} de {len(items)}")

        if st.button("Reintentar", key=f"quiz_retry_{quiz_signature}"):
            answers.clear()
            confirmed_answers.clear()
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

    # Sin prerrequisitos la sección no se muestra, para no sumar ruido al encabezado.
    prerequisites = metadata.get("prerrequisitos") or []
    if prerequisites:
        st.markdown("**Prerrequisitos**")
        for prerequisite in prerequisites:
            st.write(f"• {prerequisite}")

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
