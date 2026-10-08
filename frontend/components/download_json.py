"""Descarga e inspección del paquete educativo en JSON (NM-15)."""

import json
import re
import unicodedata
from pathlib import Path

import streamlit as st


def serializar_paquete(resultado: dict) -> bytes:
    """Serializa la respuesta del backend tal cual, sin modificarla."""
    return json.dumps(resultado, ensure_ascii=False, indent=2).encode("utf-8")


def slugify(texto: str | None, max_len: int = 50) -> str:
    """Minúsculas, sin tildes y solo [a-z0-9_], apto para nombres de archivo."""
    normalizado = unicodedata.normalize("NFKD", texto or "")
    ascii_texto = normalizado.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_texto.lower()).strip("_")
    return slug[:max_len].strip("_")


def obtener_tema(
    resultado: dict,
    titulo_documento: str | None = None,
    archivo_origen: str | None = None,
) -> str:
    """Tema del paquete: título del usuario > nombre del archivo > título generado."""
    if titulo_documento and titulo_documento.strip():
        return titulo_documento.strip()
    if archivo_origen:
        return Path(archivo_origen).stem
    return (resultado.get("contenido_adaptado") or {}).get("titulo") or ""


def nombre_archivo(tema: str, perfil: str, formato: str) -> str:
    partes = [
        slugify(tema) or "paquete",
        slugify(perfil) or "perfil",
        slugify(formato) or "formato",
    ]
    return "-".join(partes) + ".json"


def render_json_download(
    resultado: dict | None,
    titulo_documento: str | None = None,
    archivo_origen: str | None = None,
) -> None:
    if not resultado or resultado.get("status") != "exito":
        return

    metadatos = resultado.get("metadatos") or {}
    tema = obtener_tema(resultado, titulo_documento, archivo_origen)
    nombre = nombre_archivo(
        tema,
        metadatos.get("perfil_aplicado", ""),
        metadatos.get("formato_generado", ""),
    )
    datos = serializar_paquete(resultado)

    st.download_button(
        "Descargar JSON",
        data=datos,
        file_name=nombre,
        mime="application/json",
        icon=":material/download:",
    )

    with st.expander("Ver JSON crudo", expanded=False):
        # st.code ya incluye el botón de copiar al portapapeles.
        st.code(datos.decode("utf-8"), language="json")
