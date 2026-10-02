import re
import os
import json
import uuid
from typing import List, Dict, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dataia.common.models import ExtractedContent, Chunk, ChunkMetadata
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

CACHE_DIR = ".dataia_cache/chunk_metadata"

class ChunkPedagogicalInfo(BaseModel):
    tipo_contenido: str = Field(description="definicion | procedimiento | ejemplo | afirmacion | tabla | codigo")
    nivel_dificultad: int = Field(description="1 al 5")
    concepto_principal: str = Field(description="Concepto principal del chunk")

def enrich_chunk_metadata(chunk_id: str, text: str) -> ChunkPedagogicalInfo:
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{chunk_id}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ChunkPedagogicalInfo(**data)
        except Exception:
            pass

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
        structured_llm = llm.with_structured_output(ChunkPedagogicalInfo)
        
        prompt = (
            "Analiza el siguiente fragmento de texto técnico y determina su tipo de contenido, nivel de dificultad (1-5) y concepto principal.\n\n"
            f"Fragmento:\n{text}\n"
        )
        result = structured_llm.invoke(prompt)
        
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
            
        return result
    except Exception:
        return ChunkPedagogicalInfo(
            tipo_contenido="afirmacion",
            nivel_dificultad=1,
            concepto_principal="General"
        )

def _approximate_token_length(text: str) -> int:
    return int(len(text.split()) * 1.3)

class StructuralSplitter:
    def __init__(self, chunk_size=800, chunk_overlap=150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=_approximate_token_length,
            separators=["\n\n# ", "\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " ", ""]
        )
        
    def _extract_protected_blocks(self, text: str) -> Tuple[str, Dict[str, str]]:
        blocks = {}
        # Protect code blocks
        code_pattern = re.compile(r"```.*?```", re.DOTALL)
        for match in code_pattern.finditer(text):
            block = match.group(0)
            placeholder = f"__PROTECTED_BLOCK_{uuid.uuid4().hex}__"
            blocks[placeholder] = block
            text = text.replace(block, placeholder, 1)
            
        # Protect markdown tables
        table_pattern = re.compile(r"(\n\|[^\n]+\|\n\|[\s\-\|]+\|\n(?:\|[^\n]+\|\n)+)", re.MULTILINE)
        for match in table_pattern.finditer("\n" + text): # Prefix with \n to match start of table
            block = match.group(1).strip()
            if not block: continue
            placeholder = f"__PROTECTED_BLOCK_{uuid.uuid4().hex}__"
            blocks[placeholder] = block
            text = text.replace(block, placeholder, 1)
            
        return text, blocks

    def _restore_protected_blocks(self, chunks: List[str], blocks: Dict[str, str]) -> List[str]:
        restored_chunks = []
        for chunk in chunks:
            restored = chunk
            for placeholder, block in blocks.items():
                if placeholder in restored:
                    restored = restored.replace(placeholder, block)
            restored_chunks.append(restored)
        return restored_chunks
        
    def _associate_headers(self, text: str, chunks: List[str]) -> List[str]:
        # Simple header association: find nearest preceding header in original text
        # For simplicity, we just inject the current header if not present.
        current_header = ""
        header_pattern = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)
        
        headers = list(header_pattern.finditer(text))
        
        final_chunks = []
        for chunk in chunks:
            # Check if chunk contains a header
            chunk_headers = list(header_pattern.finditer(chunk))
            if chunk_headers:
                current_header = chunk_headers[0].group(0)
                final_chunks.append(chunk)
            else:
                if current_header and current_header not in chunk:
                    final_chunks.append(f"{current_header}\n\n{chunk}")
                else:
                    final_chunks.append(chunk)
        return final_chunks

    def split_text(self, text: str) -> List[str]:
        text, blocks = self._extract_protected_blocks(text)
        chunks = self.text_splitter.split_text(text)
        chunks = self._restore_protected_blocks(chunks, blocks)
        chunks = self._associate_headers(text, chunks)
        return chunks

def generate_chunk_id(doc_id: str, index: int) -> str:
    return f"{doc_id}-chk-{index:04d}"

def perform_structural_chunking(document_id: str, contents: List[ExtractedContent]) -> List[Chunk]:
    splitter = StructuralSplitter()
    chunks = []
    chunk_index = 1
    
    for content in contents:
        splits = splitter.split_text(content.text)
        
        for split_text in splits:
            chunk_id = generate_chunk_id(document_id, chunk_index)
            # Enrich metadata
            pedagogical_info = enrich_chunk_metadata(chunk_id, split_text)
            
            chunk_meta = ChunkMetadata(
                document_id=document_id,
                chunk_id=chunk_id,
                name=content.metadata.name,
                doc_type=content.metadata.doc_type,
                source=content.metadata.source,
                page=content.metadata.page,
                section=content.metadata.section,
                tipo_contenido=pedagogical_info.tipo_contenido,
                nivel_dificultad=pedagogical_info.nivel_dificultad,
                concepto_principal=pedagogical_info.concepto_principal
            )
            chunks.append(Chunk(text=split_text, metadata=chunk_meta))
            chunk_index += 1
            
    return chunks
