"""Visualización del paquete educativo generado."""

import streamlit as st

from utils.quality import requires_review


def render_flashcards(items: list[dict]) -> None:
    for number, item in enumerate(items, 1):
        with st.container(border=True):
            st.caption(f"FLASHCARD {number}")

            st.markdown("**Frente**")
            st.write(item["frente"])

            st.markdown("**Dorso**")
            st.write(item["dorso"])

            st.info(f"Pista didáctica: {item['pista_didactica']}")


def render_quiz(
    items: list[dict], claims: list[dict] | None = None, review_all: bool = False
) -> None:
    for number, item in enumerate(items, 1):
        with st.container(border=True):
            st.subheader(f"Pregunta {number}")
            observations = [claim for claim in (claims or []) if claim["item"] == number]
            needs_review = review_all or bool(observations)
            if needs_review:
                st.warning(
                    "Pregunta pendiente de revisión: su respuesta o explicación "
                    "puede no estar respaldada por el documento."
                )
                for claim in observations:
                    st.write(f"Afirmación observada: {claim['texto']}")
            st.write(item["pregunta"])

            for option in item["opciones"]:
                st.write(f"• {option}")

            with st.expander(
                "Ver respuesta y justificación",
                expanded=False,
            ):
                st.markdown(
                    "**Respuesta propuesta (requiere revisión)**"
                    if needs_review else "**Respuesta correcta**"
                )
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
    quality = result.get("evaluacion_calidad", {})
    review = requires_review(quality)
    claims = quality.get("afirmaciones_no_respaldadas") or []
    if review is True:
        st.warning(
            "Este contenido requiere revisión: puede incluir afirmaciones no "
            "respaldadas por el documento. Contrástalo con la fuente antes de utilizarlo."
        )
    elif review is None:
        st.info("Este resultado no incluye una decisión de revisión de calidad.")
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
    if output_format == "Quiz":
        render_quiz(content["items"], claims, review_all=review is True and not claims)
    elif renderer:
        renderer(content["items"])
    else:
        st.warning("El formato recibido no tiene una vista disponible.")

    st.subheader("Calidad del contenido")

    score_column, clarity_column = st.columns(2)
    score = quality.get("anclaje_fuente_score")

    score_column.metric(
        "Anclaje a la fuente",
        f"{score:.0%}" if score is not None else "No disponible",
    )
    clarity_column.metric(
        "Claridad pedagógica",
        quality.get("claridad_pedagogica", "No disponible"),
    )

    threshold = quality.get("umbral_fidelidad")
    if score is not None and threshold is not None:
        if score < threshold:
            st.markdown(f":orange[Por debajo del umbral de fidelidad ({threshold:.0%}).]")
        else:
            st.markdown(f":green[Alcanza el umbral de fidelidad ({threshold:.0%}).]")
            if review:
                st.caption("El puntaje general no descarta observaciones en afirmaciones individuales.")
    else:
        st.caption("Sin umbral informado: no se clasifica el puntaje como aprobado.")

    if claims:
        st.markdown("**Afirmaciones sin respaldo detectadas**")
        for claim in claims:
            location = "Introducción" if claim["item"] == 0 else f"Item {claim['item']}"
            st.write(f"{location}: {claim['texto']}")

    st.markdown("**Observaciones**")
    st.write(quality.get("observaciones") or "Sin observaciones.")

    st.subheader("Almacenamiento OCI")
    storage = result.get("almacenamiento_oci", {})

    if storage.get("status_upload") == "completado":
        if review is False:
            st.success("Contenido guardado en OCI.")
        else:
            st.info("Contenido guardado en OCI; el almacenamiento no certifica su calidad.")
        st.text(f"Bucket: {storage['bucket']}")
        st.text(f"Objeto: {storage['objeto_id']}")
    elif storage.get("status_upload") == "error":
        st.warning(
            "El contenido fue generado, "
             "pero no se persistió en OCI."
        )
    else:
        st.info("No se recibió confirmación de almacenamiento en OCI.")
