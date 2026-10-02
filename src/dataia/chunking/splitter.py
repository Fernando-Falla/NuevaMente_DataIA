from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dataia.common.models import ExtractedContent, Chunk, ChunkMetadata

def generate_chunk_id(doc_id: str, index: int) -> str:
    """Genera un identificador único para cada chunk atado al documento original."""
    return f"{doc_id}-chk-{index:04d}"

def _approximate_token_length(text: str) -> int:
    """
    Aproximación determinista local para conteo de tokens, 
    asumiendo ~1.3 tokens por palabra (sin depender de librerías externas pesadas 
    en esta fase a menos que se reemplace por tiktoken posteriormente).
    """
    return int(len(text.split()) * 1.3)

def perform_chunking(document_id: str, contents: List[ExtractedContent]) -> List[Chunk]:
    """
    Segmenta el texto respetando jerarquías (IA-03).
    Aplica 800 tokens max, 150 overlap usando RecursiveCharacterTextSplitter.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        length_function=_approximate_token_length,
        separators=[
            "\n\n# ",    # Título Principal
            "\n\n## ",   # Subtítulo Nivel 2
            "\n\n### ",  # Subtítulo Nivel 3
            "\n\n",      # Párrafos
            "\n",        # Saltos de línea
            ". ",        # Oraciones
            " ",         # Palabras
            ""           # Caracteres
        ]
    )

    chunks = []
    chunk_index = 1

    for content in contents:
        # Divide el texto manteniendo la coherencia de la página o sección original
        splits = text_splitter.split_text(content.text)
        
        for split_text in splits:
            # Replicamos y preservamos la metadata heredada desde IA-02
            chunk_meta = ChunkMetadata(
                document_id=document_id,
                chunk_id=generate_chunk_id(document_id, chunk_index),
                name=content.metadata.name,
                doc_type=content.metadata.doc_type,
                source=content.metadata.source,
                page=content.metadata.page,
                section=content.metadata.section
            )
            chunks.append(Chunk(text=split_text, metadata=chunk_meta))
            chunk_index += 1

    return chunks
