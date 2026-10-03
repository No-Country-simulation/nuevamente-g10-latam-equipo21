import streamlit as st


def render_tutorial(items: list[dict]) -> None:
	for index, item in enumerate(items, start=1):
		with st.expander(f"Paso {item.get('paso_numero', index)} · {item.get('titulo_paso', 'Desarrollo')}", expanded=index == 1):
			st.write(item.get("contenido", ""))
			if item.get("codigo_ejemplo"):
				st.code(item["codigo_ejemplo"])


def render_summary(items: list[dict]) -> None:
	for item in items:
		with st.container(border=True):
			st.markdown(f"### {item.get('punto_clave', 'Punto clave')}")
			st.write(item.get("descripcion", ""))
			if item.get("impacto_negocio"):
				st.caption(f"Impacto · {item['impacto_negocio']}")


def render_class_script(items: list[dict]) -> None:
	for item in items:
		duration = item.get("tiempo_estimado_minutos", 0)
		with st.expander(f"{item.get('seccion', 'Sección')} · {duration} min", expanded=True):
			st.write(item.get("narracion", ""))
			if item.get("notas_visuales"):
				st.info(f"Apoyo visual · {item['notas_visuales']}")
