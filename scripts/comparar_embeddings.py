"""
Compara modelos de embeddings para la recuperación dentro de un documento
(spec de proveedores, CA3): Gemini frente a modelos locales de fastembed.

Uso, desde la raíz del repositorio:
    uv run --system-certs python scripts/comparar_embeddings.py <documento> [<documento> ...]

- Corpus: los chunks de cada documento (ingestión y clasificación desde la caché).
- Consultas: los 3 primeros conceptos clave de la metadata de cada documento.
- Búsqueda: top-4 dentro del documento (filtro por document_id), como el pipeline.
- Juicio por pooling: por consulta, un juez de Gemini marca como relevantes o no
  los fragmentos que devolvió cualquiera de los modelos; todos se evalúan con
  las mismas etiquetas.
- Métricas: Hit@4 (al menos un relevante), Precision@4 y MRR.
El reporte se guarda en .reports/embeddings-comparacion-<fecha>.md.
"""
import datetime
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

os.environ.setdefault("IA_STRICT_PROVIDERS", "1")

from pydantic import BaseModel, Field  # noqa: E402

from dataia.chunking.service import process_chunks  # noqa: E402
from dataia.common.budget import estimate_tokens  # noqa: E402
from dataia.common.credentials import get_google_api_key  # noqa: E402
from dataia.common.providers import GENERATION_LIMITER, call_provider, create_gemini_llm  # noqa: E402
from dataia.ingestion.service import ingest_document  # noqa: E402
from dataia.vectorstore import client  # noqa: E402

MODELOS = [
    ("gemini", "models/gemini-embedding-001"),
    ("local", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
    ("local", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"),
]
TOP_K = 4


class Relevancia(BaseModel):
    relevantes: List[int] = Field(description="Números de los fragmentos que contienen información útil y directa sobre la consulta")


def juzgar(consulta: str, textos: List[str]) -> set:
    llm = create_gemini_llm(api_key=get_google_api_key()).with_structured_output(Relevancia)
    fragmentos = "\n\n".join(f"=== FRAGMENTO {i} ===\n{t}" for i, t in enumerate(textos))
    prompt = (
        f"Consulta: {consulta}\n\nIndica qué fragmentos contienen información útil y directa sobre la consulta "
        f"(definición, explicación o datos del concepto). Devuelve sus números.\n\n{fragmentos}"
    )
    resultado = call_provider("JUEZ_RELEVANCIA", lambda: llm.invoke(prompt), estimate_tokens(prompt), GENERATION_LIMITER)
    return set(resultado.relevantes) if resultado else set()


def main():
    documentos = [Path(p) for p in sys.argv[1:]]
    if not documentos:
        print(__doc__)
        sys.exit(1)

    corpus = []
    for doc in documentos:
        ingestion = ingest_document(str(doc))
        if ingestion.status != "aprobado":
            print(f"Omitido {doc.name}: {ingestion.codigo}")
            continue
        chunks = process_chunks(ingestion).chunks
        conceptos = (ingestion.pedagogical_metadata.conceptos_clave or [])[:3]
        corpus.append((doc.name, ingestion.document_id, chunks, conceptos))
        print(f"{doc.name}: {len(chunks)} chunks, consultas {conceptos}")

    base = tempfile.mkdtemp(prefix="embeddings-")
    resultados = {}  # modelo -> {(doc, consulta): [chunk_id, ...]}
    tiempos = {}
    textos = {c.metadata.chunk_id: c.text for _, _, chunks, _ in corpus for c in chunks}
    for backend, modelo in MODELOS:
        os.environ["DATAIA_EMBEDDINGS"] = backend
        os.environ["DATAIA_LOCAL_EMBEDDING_MODEL"] = modelo
        client.PERSIST_DIRECTORY = os.path.join(base, modelo.replace("/", "_"))
        inicio = time.time()
        for _, _, chunks, _ in corpus:
            client.insert_chunks(chunks)
        tiempos[modelo] = time.time() - inicio
        store = client.get_vector_store()
        resultados[modelo] = {
            (nombre, consulta): [d.metadata["chunk_id"] for d in store.similarity_search(consulta, k=TOP_K, filter={"document_id": doc_id})]
            for nombre, doc_id, _, consultas in corpus for consulta in consultas
        }
        print(f"{modelo}: indexado en {tiempos[modelo]:.0f} s")

    metricas = {modelo: {"hit": [], "precision": [], "mrr": []} for _, modelo in MODELOS}
    for clave in resultados[MODELOS[0][1]]:
        pool = list(dict.fromkeys(cid for modelo in resultados for cid in resultados[modelo][clave]))
        relevantes = {pool[i] for i in juzgar(clave[1], [textos[cid] for cid in pool]) if 0 <= i < len(pool)}
        for modelo in resultados:
            recuperados = resultados[modelo][clave]
            aciertos = [cid in relevantes for cid in recuperados]
            metricas[modelo]["hit"].append(1.0 if any(aciertos) else 0.0)
            metricas[modelo]["precision"].append(sum(aciertos) / TOP_K)
            metricas[modelo]["mrr"].append(next((1 / (i + 1) for i, a in enumerate(aciertos) if a), 0.0))

    promedio = lambda xs: sum(xs) / len(xs) if xs else 0.0
    filas = [
        f"| {modelo} | {promedio(m['hit']):.2f} | {promedio(m['precision']):.2f} | {promedio(m['mrr']):.2f} | {tiempos[modelo]:.0f} s |"
        for modelo, m in metricas.items()
    ]
    fecha = datetime.date.today().isoformat()
    reporte = PROJECT_ROOT / ".reports" / f"embeddings-comparacion-{fecha}.md"
    reporte.parent.mkdir(exist_ok=True)
    consultas = sum(len(c) for *_, c in corpus)
    reporte.write_text(
        f"# Comparación de embeddings\n\n**Fecha:** {fecha}\n**Documentos:** {len(corpus)} | **Consultas:** {consultas} | **top_k:** {TOP_K}\n\n"
        "Consultas: 3 conceptos clave por documento; búsqueda dentro del documento; juicio de relevancia por pooling con Gemini.\n\n"
        "| Modelo | Hit@4 | Precision@4 | MRR | Indexación |\n|---|---|---|---|---|\n" + "\n".join(filas) + "\n\n"
        "## Documentos\n\n" + "\n".join(f"- {n} ({len(ch)} chunks): {', '.join(c)}" for n, _, ch, c in corpus) + "\n",
        encoding="utf-8",
    )
    print("\n".join(filas))
    print(f"Reporte: {reporte.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
