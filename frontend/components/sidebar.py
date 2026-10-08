import streamlit as st


OPTIONS = {
	"perfil_destinatario": {
		"Principiante": "Principiante",
		"Desarrollador_Junior_SemiSenior": "Desarrollador · Junior / SemiSenior",
		"Lider_Tecnico_Arquitecto": "Líder técnico / Arquitecto",
		"Gestor_Ejecutivo_No_Tecnico": "Gestor ejecutivo · No técnico",
	},
	"formato_salida": {
		"Tutorial": "Tutorial paso a paso",
		"Flashcards": "Flashcards",
		"Quiz": "Quiz",
		"Resumen_Ejecutivo": "Resumen ejecutivo",
		"Guion_Clase": "Guion de clase / video",
	},
	"nicho_sector": {
		"Fintech": "Fintech",
		"Salud": "Salud",
		"Ecommerce": "Ecommerce",
		"General": "General",
	},
	"nivel_detalle": {
		"Introductorio": "Introductorio",
		"Didactico": "Didáctico",
		"Tecnico_Profundo": "Técnico profundo",
	},
}


def _select_option(field: str, label: str, default: str, *, disabled: bool) -> str:
	choices = OPTIONS[field]
	return st.selectbox(
		label,
		options=list(choices),
		index=list(choices).index(default),
		format_func=choices.get,
		disabled=disabled,
	)


def render_adaptation_options(*, has_source_document: bool) -> dict[str, str]:
	with st.sidebar:
		st.markdown('<div class="sidebar-brand">N<span>·</span>M</div>', unsafe_allow_html=True)
		st.markdown("### Parámetros del recurso")
		st.caption("Configura a quién va dirigido y cómo presentarlo.")
		disabled = not has_source_document
		profile = _select_option("perfil_destinatario", "Perfil destinatario", "Principiante", disabled=disabled)
		format_value = _select_option("formato_salida", "Formato de salida", "Tutorial", disabled=disabled)
		sector = _select_option("nicho_sector", "Nicho/Sector", "General", disabled=disabled)
		detail = _select_option("nivel_detalle", "Nivel de detalle", "Didactico", disabled=disabled)
		if disabled:
			st.caption("Carga un documento para habilitar estas opciones.")
		st.divider()
		st.markdown('<div class="sidebar-note"><span>FUENTE → CONTENIDO</span><br>La adaptación conserva el anclaje al documento original.</div>', unsafe_allow_html=True)

	return {
		"perfil_destinatario": profile,
		"formato_salida": format_value,
		"nicho_sector": sector,
		"nivel_detalle": detail,
	}
