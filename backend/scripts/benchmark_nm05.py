import time
from pathlib import Path

from app.services.chunking import chunk_pages
from app.services.embeddings import GeminiEmbeddingService
from app.services.chroma_store import ChromaStore


BENCHMARK_DIRECTORY = "./chroma_benchmark_nm05"
DOCUMENT_ID = "benchmark-10-pages"


def build_test_pages():
    base_text = (
        "Oracle Cloud Infrastructure permite crear redes virtuales, "
        "subredes públicas y privadas, gateways, tablas de rutas y "
        "reglas de seguridad. Este contenido se utiliza para probar "
        "el pipeline RAG de NuevaMente. "
    )

    return [
        {
            "page_number": page_number,
            "text": base_text * 20,
        }
        for page_number in range(1, 11)
    ]


def main():
    pages = build_test_pages()

    chunks = chunk_pages(
        document_id=DOCUMENT_ID,
        pages=pages,
        chunk_size=1000,
        chunk_overlap=200,
    )

    embedding_service = GeminiEmbeddingService()

    Path(BENCHMARK_DIRECTORY).mkdir(
        parents=True,
        exist_ok=True,
    )

    store = ChromaStore(
        embedding_service=embedding_service,
        persist_directory=BENCHMARK_DIRECTORY,
        collection_name="benchmark_nm05",
    )

    start = time.perf_counter()

    indexed = store.index_chunks(chunks)

    elapsed = time.perf_counter() - start

    stored = store.count_document(DOCUMENT_ID)

    print()
    print("=== Benchmark NM-05 ===")
    print("Paginas: 10")
    print(f"Chunks generados: {len(chunks)}")
    print(f"Chunks indexados: {indexed}")
    print(f"Chunks almacenados: {stored}")
    print(f"Tiempo total: {elapsed:.2f} segundos")

    if elapsed < 60:
        print("RESULTADO: OK - menor a 60 segundos")
    else:
        print("RESULTADO: FAIL - supera 60 segundos")


if __name__ == "__main__":
    main()