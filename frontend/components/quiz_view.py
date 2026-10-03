import streamlit as st


def render_quiz(items: list[dict]) -> None:
	generation_id = st.session_state.get("generation_id", 0)
	for index, item in enumerate(items, start=1):
		st.markdown(f'<span class="item-index">PREGUNTA {index:02d}</span>', unsafe_allow_html=True)
		selected = st.radio(
			item.get("pregunta", "Pregunta"),
			options=item.get("opciones", []),
			key=f"quiz-{generation_id}-{index}",
			label_visibility="visible",
		)
		if st.button("Comprobar respuesta", key=f"quiz-check-{generation_id}-{index}"):
			if selected == item.get("respuesta_correcta"):
				st.success("Correcto. " + item.get("justificacion", ""))
			else:
				st.error(f"La respuesta correcta es: {item.get('respuesta_correcta', '')}")
				st.caption(item.get("justificacion", ""))
		st.divider()
