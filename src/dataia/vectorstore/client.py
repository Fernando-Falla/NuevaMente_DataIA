import hashlib
import json
import os
import re
from typing import List, Optional
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from dataia.common.credentials import get_google_api_key
from dataia.common.budget import estimate_tokens
from dataia.common.providers import EMBEDDING_LIMITER, call_provider, provider_http_options
from google import genai
from dataia.common.models import Chunk, DocumentPedagogicalMetadata

# Carpeta de persistencia configurable por entorno (Local / Docker-OCI)
PERSIST_DIRECTORY = os.getenv("CHROMADB_DIR", os.path.join(os.getcwd(), ".chromadb_data"))
COLLECTION_NAME = os.getenv("CHROMADB_COLLECTION", "nuevamente_docs")
# Registro por documento (metadata pedagógica y resumen de la indexación)
DOCUMENTS_DIRECTORY = os.getenv("DATAIA_DOCUMENTS_DIR", os.path.join(os.getcwd(), ".dataia_documents"))
DEFAULT_LOCAL_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

def embeddings_backend() -> str:
    """
    'local' (por defecto: fastembed en CPU, sin cuota) o 'gemini', según DATAIA_EMBEDDINGS.
    Medición (.reports/embeddings-comparacion-2026-10-22.md): mpnet iguala a Gemini en
    Hit@4 (0,96) e indexa sin esperas por cuota.
    """
    backend = os.getenv("DATAIA_EMBEDDINGS", "local").strip().lower()
    if backend not in ("gemini", "local"):
        raise ValueError("DATAIA_EMBEDDINGS debe ser 'gemini' o 'local'.")
    return backend

def local_embedding_model() -> str:
    return os.getenv("DATAIA_LOCAL_EMBEDDING_MODEL", DEFAULT_LOCAL_EMBEDDING_MODEL)

def collection_name() -> str:
    """
    Una colección por modelo de embeddings: dimensiones distintas y vectores no
    comparables (spec proveedores R5). Gemini conserva el nombre base.
    """
    if embeddings_backend() == "gemini":
        return COLLECTION_NAME
    # Último tramo del nombre (legible) + hash del nombre completo (sin colisiones al recortar);
    # ChromaDB admite nombres de hasta 63 caracteres
    model = local_embedding_model()
    digest = hashlib.sha1(model.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", model.split("/")[-1].lower()).strip("_")
    prefix = f"{COLLECTION_NAME}__"
    return f"{prefix}{slug[: 63 - len(prefix) - 9]}_{digest}"

class LocalEmbeddings(Embeddings):
    """Embeddings en CPU con fastembed (ONNX): sin red ni cuota tras la primera descarga."""

    def __init__(self, model_name: str):
        # En Windows sin modo desarrollador, huggingface_hub no puede crear enlaces simbólicos
        # en su caché: copia los archivos y avisa en cada carga; el aviso no aporta información.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed import TextEmbedding
        cache_dir = os.getenv("DATAIA_MODELS_DIR", os.path.join(os.getcwd(), ".dataia_models"))
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> List[float]:
        return next(iter(self._model.query_embed(text))).tolist()

_local_models = {}

def get_embeddings_model():
    """
    Modelo de embeddings según DATAIA_EMBEDDINGS. Gemini requiere
    DATAIA_GOOGLE_API_KEY o GOOGLE_API_KEY; el local se carga una vez por proceso.
    """
    if embeddings_backend() == "local":
        name = local_embedding_model()
        if name not in _local_models:
            _local_models[name] = LocalEmbeddings(name)
        return _local_models[name]
    model_name = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-001")
    embeddings = GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=get_google_api_key())
    # La versión instalada no aplica request_options a embed_content: se reemplaza el
    # cliente público por uno con los límites de tiempo y reintentos del proveedor.
    embeddings.client.close()
    embeddings.client = genai.Client(api_key=get_google_api_key(), http_options=provider_http_options())
    return embeddings

def get_vector_store() -> Chroma:
    """Configura y retorna la conexión persistente a ChromaDB local."""
    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)
    embeddings = get_embeddings_model()
    return Chroma(
        collection_name=collection_name(),
        embedding_function=embeddings,
        persist_directory=PERSIST_DIRECTORY
    )

def insert_chunks(chunks: List[Chunk]) -> bool:
    """
    Recibe Chunks Pydantic (IA-03), los transforma en Documents de LangChain
    purificando metadatos (evitando nulls que rompen ChromaDB) y los persiste.
    Usa el chunk_id como id del vector: si el documento ya está indexado con los
    mismos fragmentos no recalcula embeddings; si cambió, reemplaza sus vectores.
    Devuelve True si el documento ya estaba indexado.
    """
    if not chunks:
        return False

    vectorstore = get_vector_store()
    document_id = chunks[0].metadata.document_id

    documents = []
    ids = []
    for chunk in chunks:
        # ChromaDB no soporta valores "None" en metadatos, por lo que filtramos los nulos
        # pero garantizamos que document_id, chunk_id, etc. estén siempre presentes.
        meta_dict = {k: v for k, v in chunk.metadata.model_dump().items() if v is not None}

        doc = Document(
            page_content=chunk.text,
            metadata=meta_dict
        )
        documents.append(doc)
        ids.append(chunk.metadata.chunk_id)

    existing = vectorstore.get(where={"document_id": document_id}, include=["documents", "metadatas"])
    current = {i: (text, meta) for i, text, meta in zip(existing["ids"], existing["documents"], existing["metadatas"])}
    if set(current) == set(ids) and all(current[i][0] == d.page_content for i, d in zip(ids, documents)):
        # Mismos textos implican mismos embeddings: solo se actualiza la metadata que cambió
        # (por ejemplo, una clasificación pedagógica que antes falló y usó valores por defecto)
        changed = [(i, d.metadata) for i, d in zip(ids, documents) if current[i][1] != d.metadata]
        if changed:
            vectorstore._collection.update(ids=[i for i, _ in changed], metadatas=[m for _, m in changed])
        return True

    # Reindexación idempotente: se eliminan los vectores previos del documento
    if existing and existing["ids"]:
        vectorstore.delete(ids=existing["ids"])
    # Embeddings locales: sin cuota que respetar (spec proveedores R4)
    if embeddings_backend() == "local":
        vectorstore.add_documents(documents, ids=ids)
        return False
    # Lotes propios, cada uno sujeto al control de ritmo de embeddings (spec IA-02b R5).
    # La integración de LangChain con Chroma persiste automáticamente al agregar.
    for batch, batch_ids, batch_tokens in _embedding_batches(documents, ids):
        call_provider(
            "EMBEDDINGS_DOCUMENTOS",
            lambda: vectorstore.add_documents(batch, ids=batch_ids),
            batch_tokens,
            EMBEDDING_LIMITER,
            requests=len(batch),
        )
    return False

def _embedding_batches(documents: List[Document], ids: List[str]):
    """
    Lotes de hasta DATAIA_EMBEDDING_BATCH_SIZE chunks y, como máximo, un tercio de
    los tokens por minuto de embeddings: ningún lote agota la cuota por sí solo.
    """
    max_chunks = int(os.getenv("DATAIA_EMBEDDING_BATCH_SIZE", "20"))
    max_tokens = max(1, EMBEDDING_LIMITER.limits()[1] // 3)
    batch, batch_ids, batch_tokens = [], [], 0
    for doc, doc_id in zip(documents, ids):
        tokens = estimate_tokens(doc.page_content)
        if batch and (len(batch) >= max_chunks or batch_tokens + tokens > max_tokens):
            yield batch, batch_ids, batch_tokens
            batch, batch_ids, batch_tokens = [], [], 0
        batch.append(doc)
        batch_ids.append(doc_id)
        batch_tokens += tokens
    if batch:
        yield batch, batch_ids, batch_tokens

def get_document_chunks(document_id: str) -> List[Document]:
    """
    Lectura para la etapa de generación: todos los chunks del documento, en el
    orden del documento original (no una búsqueda por similitud).
    """
    result = get_vector_store().get(where={"document_id": document_id}, include=["documents", "metadatas"])
    documents = [
        Document(page_content=text, metadata=metadata or {})
        for text, metadata in zip(result["documents"], result["metadatas"])
    ]
    return sorted(documents, key=lambda d: d.metadata.get("chunk_id", ""))

def _document_record_path(document_id: str) -> str:
    return os.path.join(DOCUMENTS_DIRECTORY, f"{document_id}.json")

def save_document_record(
    document_id: str,
    chunks: List[Chunk],
    pedagogical_metadata: Optional[DocumentPedagogicalMetadata],
) -> None:
    """Persiste la metadata del documento junto al resumen de su indexación."""
    os.makedirs(DOCUMENTS_DIRECTORY, exist_ok=True)
    first = chunks[0].metadata
    sections = list(dict.fromkeys(c.metadata.section for c in chunks if c.metadata.section))
    record = {
        "document_id": document_id,
        "name": first.name,
        "doc_type": first.doc_type,
        "collection_name": collection_name(),
        "chunks": len(chunks),
        "sections": sections,
        "pedagogical_metadata": pedagogical_metadata.model_dump() if pedagogical_metadata else None,
    }
    with open(_document_record_path(document_id), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

def load_document_record(document_id: str) -> Optional[dict]:
    """Devuelve el registro del documento o None si no fue indexado."""
    path = _document_record_path(document_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
