from dataia.common.models import ChunkingResult, VectorStoreResponse, VectorStoreResult, VectorStoreError
from dataia.vectorstore.client import insert_chunks, COLLECTION_NAME

def process_vectorstore(chunking_result: ChunkingResult) -> VectorStoreResponse:
    """
    Orquestador de IA-04:
    Toma el éxito de la fase de segmentación (ChunkingResult), genera los embeddings 
    usando Gemini, y almacena en el VectorStore preservando la trazabilidad.
    """
    try:
        if not chunking_result.chunks:
            return VectorStoreError(
                codigo="SIN_CHUNKS",
                mensaje="El resultado de chunking no contiene fragmentos para procesar."
            )

        # Genera embeddings y persiste manteniendo los metadatos de los chunks
        inserted_count = insert_chunks(chunking_result.chunks)

        return VectorStoreResult(
            document_id=chunking_result.document_id,
            chunks_inserted=inserted_count,
            collection_name=COLLECTION_NAME
        )
        
    except Exception as e:
        return VectorStoreError(
            codigo="ERROR_VECTORSTORE",
            mensaje=f"Fallo críto en almacenamiento/embeddings vectorial: {str(e)}"
        )
