from pathlib import Path

from pypdf import PdfReader

from app.core.config import settings
from app.services.chunking import chunk_pages
from app.services.chroma_store import ChromaStore
from app.services.chroma_vector_store import ChromaVectorStore
from app.services.embeddings import GeminiEmbeddingService
from app.services.fidelity_service import evaluar_fidelidad
from app.services.gemini_provider import GeminiProvider
from app.services.multi_agent_service import crear_grafo_multiagente
from app.services.orchestration_service import generar_contenido_adaptado
from app.services.retrieval_service import (
    ensamblar_contexto,
    recuperar_contexto,
)


# ============================================================
# DOCUMENTO DE DEMO PROVISIONAL
#
# Si el equipo confirma otro documento, cambiamos solamente
# estas variables y volvemos a ejecutar la comparación.
# ============================================================

DOCUMENT_PATH = Path(
    "tests/fixtures/Curso Python e Inteligencia Artificial.pdf"
)

DOCUMENT_ID = "demo-curso-python-ia"

DOCUMENT_TITLE = (
    "Curso Intensivo: Python e Inteligencia Artificial"
)

CONSULTA = (
    "Explica los principales temas del curso de Python e "
    "Inteligencia Artificial, incluyendo preprocesamiento "
    "de datos, machine learning, deep learning, "
    "IA generativa y RAG."
)

PERSIST_DIRECTORY = "./chroma_comparativa_nm_d1"


def extraer_paginas_pdf(path: Path):
    reader = PdfReader(str(path))

    return [
        {
            "page_number": numero,
            "text": page.extract_text() or "",
        }
        for numero, page in enumerate(
            reader.pages,
            start=1,
        )
    ]


def main():
    if not DOCUMENT_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el documento: {DOCUMENT_PATH}"
        )

    print()
    print("======================================")
    print(" COMPARATIVA NM-D1")
    print("======================================")
    print(f"Documento: {DOCUMENT_PATH.name}")
    print()

    # --------------------------------------------------------
    # 1. INDEXAR EL DOCUMENTO
    # --------------------------------------------------------

    pages = extraer_paginas_pdf(
        DOCUMENT_PATH
    )

    chunks = chunk_pages(
        document_id=DOCUMENT_ID,
        pages=pages,
        chunk_size=1000,
        chunk_overlap=200,
    )

    embedding_service = (
        GeminiEmbeddingService()
    )

    chroma_store = ChromaStore(
        embedding_service=embedding_service,
        persist_directory=PERSIST_DIRECTORY,
        collection_name="comparativa_nm_d1",
    )

    cantidad_indexada = (
        chroma_store.index_chunks(chunks)
    )

    vector_store = ChromaVectorStore(
        chroma_store=chroma_store,
        embedding_service=embedding_service,
    )

    llm_provider = (
        GeminiProvider.desde_configuracion()
    )

    print(
        f"Paginas detectadas: {len(pages)}"
    )
    print(
        f"Chunks indexados: {cantidad_indexada}"
    )
    print()

    # --------------------------------------------------------
    # 2. ANTES: FLUJO SIMPLE NM-08 + NM-09
    # --------------------------------------------------------

    fragmentos = recuperar_contexto(
        consulta=CONSULTA,
        vector_store=vector_store,
        documento_id=DOCUMENT_ID,
    )

    contexto = ensamblar_contexto(
        fragmentos
    )

    contenido_antes = (
        generar_contenido_adaptado(
            documento_titulo=DOCUMENT_TITLE,
            contexto_recuperado=contexto,
            perfil_destinatario="Principiante",
            formato_salida="Flashcards",
            nicho_sector="General",
            nivel_detalle="Didactico",
            llm_provider=llm_provider,
        )
    )

    evaluacion_antes = evaluar_fidelidad(
        documento_id=DOCUMENT_ID,
        contenido_adaptado=contenido_antes,
        vector_store=vector_store,
        llm_provider=llm_provider,
        perfil_destinatario="Principiante",
    )

    print("---------- ANTES ----------")
    print(
        "Score de anclaje:",
        evaluacion_antes.anclaje_fuente_score,
    )
    print(
        "Claridad:",
        evaluacion_antes.claridad_pedagogica,
    )
    print(
        "Observaciones:",
        evaluacion_antes.observaciones,
    )
    print()

    # --------------------------------------------------------
    # 3. DESPUÉS: LANGGRAPH MULTI-AGENTE NM-D1
    # --------------------------------------------------------

    grafo = crear_grafo_multiagente(
        vector_store=vector_store,
        llm_provider=llm_provider,
        max_iterations=(
            settings.MULTI_AGENT_MAX_ITERATIONS
        ),
        fidelity_threshold=(
            settings.FIDELITY_SCORE_THRESHOLD
        ),
    )

    resultado = grafo.invoke(
        {
            "documento_id": DOCUMENT_ID,
            "documento_titulo": DOCUMENT_TITLE,
            "consulta_recuperacion": CONSULTA,
            "perfil_destinatario": "Principiante",
            "formato_salida": "Flashcards",
            "nicho_sector": "General",
            "nivel_detalle": "Didactico",
            "iteracion": 0,
        }
    )

    evaluacion_despues = (
        resultado["evaluacion_calidad"]
    )

    print("---------- DESPUES ----------")
    print(
        "Score de anclaje:",
        evaluacion_despues.anclaje_fuente_score,
    )
    print(
        "Claridad:",
        evaluacion_despues.claridad_pedagogica,
    )
    print(
        "Observaciones:",
        evaluacion_despues.observaciones,
    )
    print(
        "Iteraciones del Redactor:",
        resultado["iteracion"],
    )

    print()
    print("---------- COMPARACION ----------")

    diferencia = round(
        evaluacion_despues.anclaje_fuente_score
        - evaluacion_antes.anclaje_fuente_score,
        2,
    )

    print(
        "Score antes:",
        evaluacion_antes.anclaje_fuente_score,
    )

    print(
        "Score despues:",
        evaluacion_despues.anclaje_fuente_score,
    )

    print(
        "Diferencia:",
        diferencia,
    )

    print()
    print("Comparativa NM-D1 finalizada.")


if __name__ == "__main__":
    main()