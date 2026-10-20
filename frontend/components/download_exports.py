"""Exportaciones del paquete educativo: Markdown, PDF didáctico y CSV para Anki (NM-D5)."""

from __future__ import annotations

import csv
import io

import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from components.download_json import obtener_tema, slugify


def _metadatos(resultado: dict) -> dict:
    return resultado.get("metadatos") or {}


def _contenido(resultado: dict) -> dict:
    return resultado.get("contenido_adaptado") or {}


def nombre_base(
    resultado: dict,
    titulo_documento: str | None = None,
    archivo_origen: str | None = None,
) -> str:
    """Nombre de archivo sin extensión: tema-perfil-formato."""
    metadatos = _metadatos(resultado)
    tema = obtener_tema(resultado, titulo_documento, archivo_origen)
    partes = [
        slugify(tema) or "paquete",
        slugify(metadatos.get("perfil_aplicado", "")) or "perfil",
        slugify(metadatos.get("formato_generado", "")) or "formato",
    ]
    return "-".join(partes)


# --- Markdown ---------------------------------------------------------------


def _items_markdown(items: list[dict], formato: str) -> list[str]:
    lineas: list[str] = []
    for numero, item in enumerate(items, 1):
        if formato == "Flashcards":
            lineas.append(f"### {numero}. {item.get('frente', '')}")
            lineas.append("")
            lineas.append(f"**Dorso:** {item.get('dorso', '')}")
            lineas.append("")
            lineas.append(f"> Pista didáctica: {item.get('pista_didactica', '')}")
        elif formato == "Quiz":
            lineas.append(f"### Pregunta {numero}")
            lineas.append("")
            lineas.append(item.get("pregunta", ""))
            lineas.append("")
            for opcion in item.get("opciones", []):
                lineas.append(f"- {opcion}")
            lineas.append("")
            lineas.append(f"**Respuesta correcta:** {item.get('respuesta_correcta', '')}")
            lineas.append("")
            lineas.append(f"**Justificación:** {item.get('justificacion', '')}")
        elif formato == "Tutorial":
            lineas.append(
                f"### Paso {item.get('paso_numero', numero)}: {item.get('titulo_paso', '')}"
            )
            lineas.append("")
            lineas.append(item.get("contenido", ""))
            if item.get("codigo_ejemplo"):
                lineas.append("")
                lineas.append("```")
                lineas.append(item["codigo_ejemplo"])
                lineas.append("```")
        elif formato == "Resumen_Ejecutivo":
            lineas.append(f"### {item.get('punto_clave', '')}")
            lineas.append("")
            lineas.append(item.get("descripcion", ""))
            lineas.append("")
            lineas.append(f"**Impacto de negocio:** {item.get('impacto_negocio', '')}")
        elif formato == "Guion_Clase":
            lineas.append(
                f"### {item.get('seccion', '')} "
                f"({item.get('tiempo_estimado_minutos', 0)} min)"
            )
            lineas.append("")
            lineas.append(item.get("narracion", ""))
            if item.get("notas_visuales"):
                lineas.append("")
                lineas.append(f"**Notas visuales:** {item['notas_visuales']}")
        lineas.append("")
    return lineas


def construir_markdown(resultado: dict) -> str:
    """Genera un `.md` legible con encabezados y la estructura del paquete."""
    contenido = _contenido(resultado)
    metadatos = _metadatos(resultado)

    lineas = [f"# {contenido.get('titulo', 'Paquete educativo')}", ""]
    introduccion = contenido.get("introduccion_contextualizada", "")
    if introduccion:
        lineas += [introduccion, ""]

    lineas += [
        "## Metadatos",
        "",
        f"- **Perfil aplicado:** {metadatos.get('perfil_aplicado', '')}",
        f"- **Formato:** {metadatos.get('formato_generado', '')}",
        (
            "- **Tiempo estimado de estudio:** "
            f"{metadatos.get('tiempo_estimado_estudio_minutos', 0)} min"
        ),
    ]
    conceptos = metadatos.get("conceptos_clave") or []
    if conceptos:
        lineas.append("- **Conceptos clave:**")
        lineas += [f"  - {concepto}" for concepto in conceptos]
    prerrequisitos = metadatos.get("prerrequisitos") or []
    if prerrequisitos:
        lineas.append("- **Prerrequisitos:**")
        lineas += [f"  - {prerrequisito}" for prerrequisito in prerrequisitos]

    lineas += ["", "## Contenido", ""]
    lineas += _items_markdown(
        contenido.get("items", []),
        metadatos.get("formato_generado", ""),
    )
    return "\n".join(lineas).rstrip() + "\n"


# --- CSV Anki ---------------------------------------------------------------


def anki_disponible(resultado: dict) -> bool:
    """La exportación a Anki solo aplica al formato Flashcards."""
    return _metadatos(resultado).get("formato_generado") == "Flashcards"


def construir_anki_csv(resultado: dict) -> str | None:
    """CSV importable en Anki (columnas frente y dorso). None si no es Flashcards.

    Usa el encabezado de importación de Anki para que las líneas iniciales no se
    interpreten como tarjetas.
    """
    if not anki_disponible(resultado):
        return None
    filas = io.StringIO()
    escritor = csv.writer(filas, lineterminator="\n")
    for item in _contenido(resultado).get("items", []):
        escritor.writerow([item.get("frente", ""), item.get("dorso", "")])
    return "#separator:comma\n#columns:frente,dorso\n" + filas.getvalue()


# --- PDF --------------------------------------------------------------------


_REEMPLAZOS_LATIN1 = str.maketrans(
    {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2026": "...",
        "\u2192": "->",
        "\u2265": ">=",
        "\u2264": "<=",
    }
)


def _pdf_texto(texto: str) -> str:
    """Normaliza tipografía común y reemplaza lo que no entra en latin-1."""
    return (
        str(texto)
        .translate(_REEMPLAZOS_LATIN1)
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _parrafo(
    pdf: FPDF,
    texto: str,
    *,
    alto: float = 6,
    estilo: str = "",
    tamano: int = 10,
    fuente: str = "Helvetica",
) -> None:
    """Escribe un párrafo y deja el cursor al inicio de la línea siguiente."""
    pdf.set_font(fuente, estilo, tamano)
    pdf.multi_cell(
        0,
        alto,
        _pdf_texto(texto),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def _pdf_items(pdf: FPDF, items: list[dict], formato: str) -> None:
    for numero, item in enumerate(items, 1):
        if formato == "Flashcards":
            _parrafo(
                pdf,
                f"{numero}. {item.get('frente', '')}",
                alto=7,
                estilo="B",
                tamano=12,
            )
            _parrafo(pdf, f"Dorso: {item.get('dorso', '')}")
            if item.get("pista_didactica"):
                _parrafo(pdf, f"Pista: {item['pista_didactica']}")
        elif formato == "Quiz":
            _parrafo(
                pdf,
                f"Pregunta {numero}: {item.get('pregunta', '')}",
                alto=7,
                estilo="B",
                tamano=12,
            )
            for opcion in item.get("opciones", []):
                _parrafo(pdf, f"- {opcion}")
            _parrafo(pdf, f"Respuesta correcta: {item.get('respuesta_correcta', '')}")
            _parrafo(pdf, f"Justificación: {item.get('justificacion', '')}")
        elif formato == "Tutorial":
            _parrafo(
                pdf,
                (
                    f"Paso {item.get('paso_numero', numero)}: "
                    f"{item.get('titulo_paso', '')}"
                ),
                alto=7,
                estilo="B",
                tamano=12,
            )
            _parrafo(pdf, item.get("contenido", ""))
            if item.get("codigo_ejemplo"):
                _parrafo(
                    pdf,
                    item["codigo_ejemplo"],
                    alto=5,
                    fuente="Courier",
                    tamano=9,
                )
        elif formato == "Resumen_Ejecutivo":
            _parrafo(pdf, item.get("punto_clave", ""), alto=7, estilo="B", tamano=12)
            _parrafo(pdf, item.get("descripcion", ""))
            _parrafo(pdf, f"Impacto de negocio: {item.get('impacto_negocio', '')}")
        elif formato == "Guion_Clase":
            _parrafo(
                pdf,
                (
                    f"{item.get('seccion', '')} "
                    f"({item.get('tiempo_estimado_minutos', 0)} min)"
                ),
                alto=7,
                estilo="B",
                tamano=12,
            )
            _parrafo(pdf, item.get("narracion", ""))
            if item.get("notas_visuales"):
                _parrafo(pdf, f"Notas visuales: {item['notas_visuales']}")
        pdf.ln(3)


def construir_pdf(resultado: dict) -> bytes:
    """PDF paginado con el contenido formateado."""
    contenido = _contenido(resultado)
    metadatos = _metadatos(resultado)
    formato = metadatos.get("formato_generado", "")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _parrafo(
        pdf,
        contenido.get("titulo", "Paquete educativo"),
        alto=10,
        estilo="B",
        tamano=18,
    )
    pdf.ln(2)

    introduccion = contenido.get("introduccion_contextualizada", "")
    if introduccion:
        _parrafo(pdf, introduccion, tamano=11)
        pdf.ln(2)

    _parrafo(pdf, "Metadatos", alto=8, estilo="B", tamano=13)
    _parrafo(
        pdf,
        (
            f"Perfil: {metadatos.get('perfil_aplicado', '')} | "
            f"Formato: {formato} | "
            f"Tiempo estimado: {metadatos.get('tiempo_estimado_estudio_minutos', 0)} min"
        ),
    )
    pdf.ln(3)

    _pdf_items(pdf, contenido.get("items", []), formato)
    return bytes(pdf.output())


# --- UI ---------------------------------------------------------------------


def render_export_buttons(
    resultado: dict | None,
    titulo_documento: str | None = None,
    archivo_origen: str | None = None,
) -> None:
    if not resultado or resultado.get("status") != "exito":
        return

    base = nombre_base(resultado, titulo_documento, archivo_origen)

    st.markdown("**Exportar el paquete**")
    columnas = st.columns(3)

    columnas[0].download_button(
        "Markdown",
        data=construir_markdown(resultado).encode("utf-8"),
        file_name=f"{base}.md",
        mime="text/markdown",
    )

    columnas[1].download_button(
        "PDF",
        data=construir_pdf(resultado),
        file_name=f"{base}.pdf",
        mime="application/pdf",
    )

    anki = construir_anki_csv(resultado)
    if anki is not None:
        columnas[2].download_button(
            "CSV Anki",
            data=anki.encode("utf-8"),
            file_name=f"{base}-anki.csv",
            mime="text/csv",
        )
    else:
        columnas[2].download_button(
            "CSV Anki",
            data=b"",
            file_name=f"{base}-anki.csv",
            mime="text/csv",
            disabled=True,
        )
        columnas[2].caption(
            "La exportación a CSV de Anki solo está disponible para el formato Flashcards."
        )
