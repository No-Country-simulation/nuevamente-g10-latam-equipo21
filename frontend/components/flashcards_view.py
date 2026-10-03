import streamlit as st


def render_flashcards(items: list[dict]) -> None:
	for index, item in enumerate(items, start=1):
		with st.container(border=True):
			st.markdown(f'<span class="item-index">TARJETA {index:02d}</span>', unsafe_allow_html=True)
			st.markdown(f"### {item.get('frente', 'Concepto')}")
			with st.expander("Ver respuesta"):
				st.write(item.get("dorso", ""))
				if item.get("pista_didactica"):
					st.caption(f"Pista · {item['pista_didactica']}")
