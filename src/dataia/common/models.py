from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Union

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

Dominio = Literal["TI", "Fintech", "Salud", "Marketing digital", "Otro"]
DOMINIOS_SOPORTADOS = ("TI", "Fintech", "Salud", "Marketing digital")

class DocumentPedagogicalMetadata(BaseModel):
    document_id: str
    conceptos_clave: List[str] = Field(default_factory=list)
    prerequisitos: List[str] = Field(default_factory=list)
    resumen_ejecutivo: str = ""
    nicho_sugerido: str = "General"
    # Spec IA-02c: None significa que el LLM no clasificó el dominio (se usa el léxico de respaldo)
    dominio: Optional[Dominio] = Field(default=None, description="Dominio del documento: TI, Fintech, Salud, Marketing digital u Otro")
    es_documento_tecnico: Optional[bool] = Field(default=None, description="True si es material técnico o profesional del dominio; False si es divulgación general, ficción, recetas, etc.")
    justificacion_dominio: str = Field(default="", description="Una frase que justifique el dominio y si es técnico")

class IngestionResult(BaseModel):
    status: str = "aprobado"
    document_id: str
    content: List[ExtractedContent]
    pedagogical_metadata: Optional[DocumentPedagogicalMetadata] = None
    # Estimación local de tokens del documento normalizado (spec IA-02b R6)
    estimated_tokens: Optional[int] = None

# El contrato de respuesta puede ser un éxito o un error controlado
IngestionResponse = Union[IngestionResult, IngestionError]

class ChunkMetadata(BaseModel):
    document_id: str
    chunk_id: str
    name: str
    doc_type: str
    source: Optional[str] = None
    page: Optional[int] = None
    page_end: Optional[int] = None # Última página que abarca el chunk (los chunks pueden cruzar páginas)
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
    # Se propaga desde IA-02 para que IA-04 la persista junto a los vectores
    pedagogical_metadata: Optional[DocumentPedagogicalMetadata] = None

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
    # True si el documento ya estaba indexado con los mismos fragmentos (no se recalcularon embeddings)
    already_indexed: bool = False

VectorStoreResponse = Union[VectorStoreResult, VectorStoreError]
