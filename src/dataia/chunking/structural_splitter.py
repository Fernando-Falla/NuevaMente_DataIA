import re
import os
import json
import uuid
import hashlib
import logging
from bisect import bisect_right
from typing import List, Dict, Literal, NamedTuple, Optional, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dataia.common.credentials import get_google_api_key
from dataia.common.models import ExtractedContent, Chunk, ChunkMetadata
from dataia.common.budget import estimate_tokens
from dataia.common.providers import call_provider, create_stage_llm
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# La caché se indexa por el hash del texto del chunk: es válida aunque cambien los ids
CACHE_DIR = os.path.join(os.getenv("DATAIA_CACHE_DIR", ".dataia_cache"), "chunk_metadata")
# Fragmentos clasificados por llamada al LLM
BATCH_SIZE = max(1, int(os.getenv("DATAIA_ENRICH_BATCH_SIZE", "15")))
# Las páginas se unen como párrafos para que un concepto pueda cruzar de página
PAGE_JOINER = "\n\n"

CODE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
HEADER_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)

TipoContenido = Literal["definicion", "procedimiento", "ejemplo", "afirmacion", "tabla", "codigo"]

class ChunkPedagogicalInfo(BaseModel):
    tipo_contenido: TipoContenido = Field(description="definicion | procedimiento | ejemplo | afirmacion | tabla | codigo")
    nivel_dificultad: int = Field(ge=1, le=5, description="1 al 5")
    concepto_principal: str = Field(description="Concepto principal del chunk")

class ChunkPedagogicalItem(ChunkPedagogicalInfo):
    indice: int = Field(description="Número del fragmento analizado")

class ChunkPedagogicalBatch(BaseModel):
    fragmentos: List[ChunkPedagogicalItem]

def _default_info() -> ChunkPedagogicalInfo:
    return ChunkPedagogicalInfo(tipo_contenido="afirmacion", nivel_dificultad=1, concepto_principal="General")

def _strict() -> bool:
    return os.getenv("IA_STRICT_PROVIDERS") == "1"

def _get_llm(schema, prompt: str):
    # Etapa CLASIFICACION: Gemini o Groq según IA_PROVIDER_CLASIFICACION y el tamaño del prompt
    return create_stage_llm("CLASIFICACION", schema, gemini_api_key=get_google_api_key(), prompt_tokens=estimate_tokens(prompt))

def _cache_file(text: str) -> str:
    return os.path.join(CACHE_DIR, f"{hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]}.json")

def _read_cache(text: str) -> Optional[ChunkPedagogicalInfo]:
    cache_file = _cache_file(text)
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return ChunkPedagogicalInfo(**json.load(f))
    except Exception:
        return None

def _write_cache(text: str, info: ChunkPedagogicalInfo) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_file(text), "w", encoding="utf-8") as f:
        f.write(info.model_dump_json(indent=2))

def enrich_chunk_metadata(chunk_id: str, text: str) -> ChunkPedagogicalInfo:
    """Clasifica un único fragmento. Se usa para los que falten en una respuesta por lotes."""
    cached = _read_cache(text)
    if cached is not None:
        return cached

    try:
        prompt = (
            "Analiza el siguiente fragmento de texto técnico y determina su tipo de contenido, nivel de dificultad (1-5) y concepto principal.\n\n"
            f"Fragmento:\n{text}\n"
        )
        structured_llm, limiter = _get_llm(ChunkPedagogicalInfo, prompt)
        result = call_provider("ENRIQUECIMIENTO_FRAGMENTO", lambda: structured_llm.invoke(prompt), estimate_tokens(prompt), limiter)
        if result is None:
            raise ValueError("El LLM no devolvió una clasificación válida.")
        _write_cache(text, result)
        return result
    except Exception as e:
        if _strict():
            raise
        logger.warning("Clasificación de un chunk no disponible; se usan valores por defecto (%s: %s)", type(e).__name__, str(e)[:200])
        return _default_info()

def _enrich_batch(texts: List[str]) -> Dict[int, ChunkPedagogicalInfo]:
    """Clasifica varios fragmentos en una sola llamada; devuelve los que el LLM respondió."""
    fragmentos = "\n\n".join(f"=== FRAGMENTO {i} ===\n{text}" for i, text in enumerate(texts))
    prompt = (
        "Analiza cada uno de los siguientes fragmentos de un documento técnico. Para cada fragmento devuelve "
        "su número (indice), su tipo de contenido (definicion, procedimiento, ejemplo, afirmacion, tabla o codigo), "
        "su nivel de dificultad (1-5) y su concepto principal. Responde una entrada por fragmento.\n\n"
        f"{fragmentos}\n"
    )
    structured_llm, limiter = _get_llm(ChunkPedagogicalBatch, prompt)
    result = call_provider("ENRIQUECIMIENTO_FRAGMENTOS_LOTE", lambda: structured_llm.invoke(prompt), estimate_tokens(prompt), limiter)
    if result is None:
        return {}
    return {
        item.indice: ChunkPedagogicalInfo(**item.model_dump(exclude={"indice"}))
        for item in result.fragmentos
        if 0 <= item.indice < len(texts)
    }

def enrich_chunks_metadata(texts: List[str]) -> List[ChunkPedagogicalInfo]:
    """
    Clasifica los fragmentos en lotes de BATCH_SIZE, reutilizando la caché.
    Los fragmentos omitidos por el LLM en un lote se reintentan individualmente.
    """
    results: List[Optional[ChunkPedagogicalInfo]] = [_read_cache(text) for text in texts]
    pending = [i for i, info in enumerate(results) if info is None]

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        try:
            found = _enrich_batch([texts[i] for i in batch])
        except Exception as e:
            if _strict():
                raise
            # Sin proveedor disponible no tiene sentido reintentar uno a uno
            logger.warning(
                "Clasificación de %d chunks no disponible; se usan valores por defecto (%s: %s)",
                len(batch), type(e).__name__, str(e)[:200],
            )
            for i in batch:
                results[i] = _default_info()
            continue
        for local_index, i in enumerate(batch):
            info = found.get(local_index)
            if info is None:
                info = enrich_chunk_metadata("", texts[i])
            else:
                _write_cache(texts[i], info)
            results[i] = info

    return results

def _approximate_token_length(text: str) -> int:
    return int(len(text.split()) * 1.3)

def _clean_header_title(title: str) -> str:
    return re.sub(r"[*_`]+", "", title).strip()

class SplitPiece(NamedTuple):
    text: str              # Texto final del chunk (con el título de su sección si se antepuso)
    start: int             # Posición del chunk en el texto original
    end: int
    section: Optional[str]

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
        for match in CODE_PATTERN.finditer(text):
            block = match.group(0)
            placeholder = f"__PROTECTED_BLOCK_{uuid.uuid4().hex}__"
            blocks[placeholder] = block
            text = text.replace(block, placeholder, 1)

        # Protect markdown tables
        table_pattern = re.compile(r"(\n\|[^\n]+\|\n\|[\s\-\|:]+\|\n(?:\|[^\n]+\|\n?)+)", re.MULTILINE)
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

    def _header_positions(self, text: str) -> List[Tuple[int, str]]:
        # Los bloques de código se enmascaran conservando las posiciones,
        # para que un comentario "# ..." no se confunda con un título.
        masked = CODE_PATTERN.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
        return [(m.start(), m.group(0)) for m in HEADER_PATTERN.finditer(masked)]

    def _locate_chunks(self, text: str, chunks: List[str]) -> List[int]:
        # Los chunks son subcadenas del texto original; el solapamiento obliga
        # a buscar cada uno a partir del inicio del anterior.
        starts = []
        cursor = 0
        for chunk in chunks:
            pos = text.find(chunk, cursor)
            if pos == -1:
                pos = text.find(chunk[:200], cursor)
            if pos == -1:
                pos = cursor
            starts.append(pos)
            cursor = pos + 1
        return starts

    def split_with_sections(self, text: str) -> List[SplitPiece]:
        protected_text, blocks = self._extract_protected_blocks(text)
        chunks = self.text_splitter.split_text(protected_text)
        chunks = self._restore_protected_blocks(chunks, blocks)
        starts = self._locate_chunks(text, chunks)
        headers = self._header_positions(text)
        header_offsets = [offset for offset, _ in headers]

        pieces = []
        for chunk, start in zip(chunks, starts):
            if HEADER_PATTERN.fullmatch(chunk.strip()):
                # Un título aislado no aporta contenido: los chunks siguientes ya lo llevan antepuesto
                continue
            index = bisect_right(header_offsets, start) - 1
            header_line = headers[index][1] if index >= 0 else None
            final_text = chunk
            if header_line and not chunk.startswith(header_line):
                # Se antepone el título de la sección a la que pertenece el inicio del chunk
                final_text = f"{header_line}\n\n{chunk}"
            section = _clean_header_title(HEADER_PATTERN.match(header_line).group(2)) if header_line else None
            pieces.append(SplitPiece(final_text, start, start + len(chunk), section or None))
        return pieces

    def split_text(self, text: str) -> List[str]:
        return [piece.text for piece in self.split_with_sections(text)]

def generate_chunk_id(doc_id: str, index: int) -> str:
    return f"{doc_id}-chk-{index:04d}"

def _page_at(page_offsets: List[int], pages: List[Optional[int]], position: int) -> Optional[int]:
    index = bisect_right(page_offsets, position) - 1
    return pages[max(index, 0)]

def perform_structural_chunking(document_id: str, contents: List[ExtractedContent]) -> List[Chunk]:
    """
    Segmenta el documento completo (no página por página), de modo que un
    concepto que cruza un salto de página no quede partido sin solapamiento.
    Cada chunk conserva la página donde empieza (page) y donde termina (page_end).
    """
    if not contents:
        return []

    page_offsets: List[int] = []
    pages: List[Optional[int]] = []
    offset = 0
    for content in contents:
        page_offsets.append(offset)
        pages.append(content.metadata.page)
        offset += len(content.text) + len(PAGE_JOINER)
    full_text = PAGE_JOINER.join(content.text for content in contents)

    pieces = StructuralSplitter().split_with_sections(full_text)
    infos = enrich_chunks_metadata([piece.text for piece in pieces])
    source_meta = contents[0].metadata

    chunks = []
    for chunk_index, (piece, pedagogical_info) in enumerate(zip(pieces, infos), start=1):
        chunk_meta = ChunkMetadata(
            document_id=document_id,
            chunk_id=generate_chunk_id(document_id, chunk_index),
            name=source_meta.name,
            doc_type=source_meta.doc_type,
            source=source_meta.source,
            page=_page_at(page_offsets, pages, piece.start),
            page_end=_page_at(page_offsets, pages, max(piece.end - 1, piece.start)),
            section=piece.section,
            tipo_contenido=pedagogical_info.tipo_contenido,
            nivel_dificultad=pedagogical_info.nivel_dificultad,
            concepto_principal=pedagogical_info.concepto_principal
        )
        chunks.append(Chunk(text=piece.text, metadata=chunk_meta))

    return chunks
