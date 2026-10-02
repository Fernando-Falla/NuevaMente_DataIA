import os
from typing import List
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from dataia.common.models import Chunk

# Carpeta de persistencia configurable por entorno (Local / Docker-OCI)
PERSIST_DIRECTORY = os.getenv("CHROMADB_DIR", os.path.join(os.getcwd(), ".chromadb_data"))
COLLECTION_NAME = os.getenv("CHROMADB_COLLECTION", "nuevamente_docs")

def get_embeddings_model():
    """Inicializa el modelo de Embeddings de Gemini (requiere GOOGLE_API_KEY en entorno)."""
    model_name = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-001")
    return GoogleGenerativeAIEmbeddings(model=model_name)

def get_vector_store() -> Chroma:
    """Configura y retorna la conexión persistente a ChromaDB local."""
    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)
    embeddings = get_embeddings_model()
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIRECTORY
    )

def insert_chunks(chunks: List[Chunk]) -> int:
    """
    Recibe Chunks Pydantic (IA-03), los transforma en Documents de LangChain 
    purificando metadatos (evitando nulls que rompen ChromaDB) y los persiste.
    """
    vectorstore = get_vector_store()
    
    documents = []
    for chunk in chunks:
        # ChromaDB no soporta valores "None" en metadatos, por lo que filtramos los nulos
        # pero garantizamos que document_id, chunk_id, etc. estén siempre presentes.
        meta_dict = {k: v for k, v in chunk.metadata.model_dump().items() if v is not None}
        
        doc = Document(
            page_content=chunk.text,
            metadata=meta_dict
        )
        documents.append(doc)
    
    if documents:
        # La integración de LangChain con Chroma persiste automáticamente al agregar
        vectorstore.add_documents(documents)
        
    return len(documents)
