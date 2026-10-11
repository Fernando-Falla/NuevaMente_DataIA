from dataia.common.models import IngestionResult, ChunkingResponse, ChunkingResult, ChunkingError
from dataia.chunking.structural_splitter import perform_structural_chunking

def process_chunks(ingestion_result: IngestionResult) -> ChunkingResponse:
    """
    Orquestador de IA-03:
    Recibe el resultado validado de IA-02 (IngestionResult), procesa el texto
    preservando trazabilidad y retorna un contrato estructurado Pydantic.
    """
    try:
        # Validar que exista contenido para evitar fallas silenciosas
        if not ingestion_result.content:
            return ChunkingError(
                codigo="SIN_CONTENIDO",
                mensaje="El resultado de ingestión no contiene texto para procesar."
            )
        
        # Generar chunks estructuralmente conscientes (IA-03 reapertura)
        chunks = perform_structural_chunking(
            document_id=ingestion_result.document_id,
            contents=ingestion_result.content
        )
        
        if not chunks:
            return ChunkingError(
                codigo="CHUNKING_FALLIDO",
                mensaje="No se logró generar ningún fragmento a partir del contenido provisto."
            )
            
        return ChunkingResult(
            document_id=ingestion_result.document_id,
            chunks=chunks,
            pedagogical_metadata=ingestion_result.pedagogical_metadata
        )
        
    except Exception as e:
        return ChunkingError(
            codigo="ERROR_INTERNO_CHUNKING",
            mensaje=f"Error inesperado durante la segmentación del documento: {str(e)}"
        )
