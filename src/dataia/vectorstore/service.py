from dataia.common.models import ChunkingResult, VectorStoreResponse, VectorStoreResult, VectorStoreError
from dataia.vectorstore.client import insert_chunks, save_document_record, COLLECTION_NAME

def process_vectorstore(chunking_result: ChunkingResult) -> VectorStoreResponse:
    """
    Orquestador de IA-04:
    Toma el éxito de la fase de segmentación (ChunkingResult), genera los embeddings
    usando Gemini, y almacena en el VectorStore preservando la trazabilidad.
    También registra la metadata pedagógica del documento para la etapa de generación.
    """
    try:
        if not chunking_result.chunks:
            return VectorStoreError(
                codigo="SIN_CHUNKS",
                mensaje="El resultado de chunking no contiene fragmentos para procesar."
            )

        # Genera embeddings y persiste manteniendo los metadatos de los chunks
        already_indexed = insert_chunks(chunking_result.chunks)
        save_document_record(
            chunking_result.document_id,
            chunking_result.chunks,
            chunking_result.pedagogical_metadata,
        )

        return VectorStoreResult(
            document_id=chunking_result.document_id,
            chunks_inserted=len(chunking_result.chunks),
            collection_name=COLLECTION_NAME,
            already_indexed=already_indexed
        )

    except Exception as e:
        return VectorStoreError(
            codigo="ERROR_VECTORSTORE",
            mensaje=f"Fallo críto en almacenamiento/embeddings vectorial: {str(e)}"
        )
