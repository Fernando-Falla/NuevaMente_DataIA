from pydantic import BaseModel, Field
from typing import Optional, List, Union

class DocumentMetadata(BaseModel):
    document_id: str
    name: str
    doc_type: str
    source: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None

class ExtractedContent(BaseModel):
    text: str
    metadata: DocumentMetadata

class IngestionError(BaseModel):
    status: str = "rechazado"
    codigo: str
    mensaje: str

class DocumentPedagogicalMetadata(BaseModel):
    document_id: str
    conceptos_clave: List[str] = Field(default_factory=list)
    prerequisitos: List[str] = Field(default_factory=list)
    resumen_ejecutivo: str = ""
    nicho_sugerido: str = "General"

class IngestionResult(BaseModel):
    status: str = "aprobado"
    document_id: str
    content: List[ExtractedContent]
    pedagogical_metadata: Optional[DocumentPedagogicalMetadata] = None

# El contrato de respuesta puede ser un éxito o un error controlado
IngestionResponse = Union[IngestionResult, IngestionError]

class ChunkMetadata(BaseModel):
    document_id: str
    chunk_id: str
    name: str
    doc_type: str
    source: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    tipo_contenido: str = "afirmacion" # definicion | procedimiento | ejemplo | afirmacion | tabla | codigo
    nivel_dificultad: int = 1
    concepto_principal: Optional[str] = None

class Chunk(BaseModel):
    text: str
    metadata: ChunkMetadata

class ChunkingError(BaseModel):
    status: str = "rechazado"
    codigo: str
    mensaje: str

class ChunkingResult(BaseModel):
    status: str = "aprobado"
    document_id: str
    chunks: List[Chunk]

ChunkingResponse = Union[ChunkingResult, ChunkingError]

class VectorStoreError(BaseModel):
    status: str = "rechazado"
    codigo: str
    mensaje: str

class VectorStoreResult(BaseModel):
    status: str = "aprobado"
    document_id: str
    chunks_inserted: int
    collection_name: str

VectorStoreResponse = Union[VectorStoreResult, VectorStoreError]
