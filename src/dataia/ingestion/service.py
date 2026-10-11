import hashlib
import logging
import os
import re
from typing import List, Optional, Union
import pymupdf

from dataia.common.models import (
    DocumentMetadata, ExtractedContent, IngestionResult, IngestionError, IngestionResponse
)
from dataia.ingestion.validators import validate_content_not_empty, validate_technical_relevance
from dataia.ingestion.normalizer import normalize_text

logger = logging.getLogger(__name__)

# Artefactos que pymupdf4llm inserta y que no aportan contenido técnico
_PAGE_SEPARATOR = re.compile(r"\n*-{5,}\s*$")
_PICTURE_PLACEHOLDER = re.compile(r"^.*==> picture .* intentionally omitted <==.*$\n?", re.MULTILINE)
# [texto](url) -> texto: las URLs son ruido para los embeddings y para el LLM
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\((?:[^()\s]|\([^)]*\))*\)")
# Proporción mínima de palabras del Markdown frente al texto plano de la misma página.
# pymupdf4llm omite el texto superpuesto a imágenes o gráficos (p. ej. páginas web
# impresas a PDF); por debajo de este umbral la página se extrae como texto plano.
MIN_MARKDOWN_COVERAGE = 0.9
# Una línea presente en esta proporción de páginas se considera encabezado/pie repetido
REPEATED_LINE_RATIO = 0.6
# Líneas con contenido que se revisan al inicio y al final de cada página
EDGE_LINES = 3
_PAGE_COUNTER = re.compile(r"^(.*?)(?:p[aá]g(?:ina)?\.?|page)?\s*\d+\s*(?:/|de|of)\s*\d+$", re.IGNORECASE)

def generate_document_id(file_path: str) -> str:
    """
    Genera el identificador del documento a partir del hash de su contenido.
    El mismo archivo produce siempre el mismo id: evita vectores duplicados en
    ChromaDB, reutiliza la caché de enriquecimiento y permite generar varios
    formatos/perfiles a partir de una única ingestión.
    """
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return f"doc-{digest.hexdigest()[:16]}"

def _page_markdown(pymupdf4llm, pdf_document, page_num: int, hdr_info) -> str:
    try:
        # Se ignoran imágenes y gráficos para no perder el texto superpuesto a ellos.
        # Costo: las tablas dibujadas con líneas se extraen como texto, sin cuadrícula.
        text = pymupdf4llm.to_markdown(
            pdf_document, pages=[page_num], hdr_info=hdr_info, show_progress=False,
            ignore_images=True, ignore_graphics=True,
        )
    except TypeError:
        # Versiones de pymupdf4llm con otra firma
        text = pymupdf4llm.to_markdown(pdf_document, pages=[page_num])
    text = _PICTURE_PLACEHOLDER.sub("", text)
    text = _MARKDOWN_LINK.sub(r"\1", text)
    return _PAGE_SEPARATOR.sub("", text)

def _line_key(line: str) -> str:
    # Solo el contador de página puede variar entre páginas ("1/8", "Página 2 de 8", "3");
    # cualquier otra diferencia, incluso numérica, hace distinta la línea.
    line = line.strip()
    if re.fullmatch(r"\d{1,4}", line):
        return "<pagina>"
    match = _PAGE_COUNTER.match(line)
    return f"{match.group(1).strip()} <pagina>" if match else line

def _edge_line_indexes(lines: List[str]) -> List[int]:
    # Encabezados y pies: solo las primeras y últimas líneas con contenido de la página
    filled = [i for i, line in enumerate(lines) if line.strip()]
    return filled[:EDGE_LINES] + filled[-EDGE_LINES:]

def _remove_repeated_lines(texts: List[str]) -> List[str]:
    """Elimina encabezados y pies que se repiten en la mayoría de las páginas."""
    if len(texts) < 3:
        return texts
    pages = [text.split("\n") for text in texts]
    counts = {}
    for lines in pages:
        for key in {_line_key(lines[i]) for i in _edge_line_indexes(lines)}:
            counts[key] = counts.get(key, 0) + 1
    threshold = max(3, REPEATED_LINE_RATIO * len(texts))
    repeated = {key for key, count in counts.items() if count >= threshold}
    if not repeated:
        return texts
    cleaned = []
    for lines in pages:
        drop = {i for i in _edge_line_indexes(lines) if _line_key(lines[i]) in repeated}
        cleaned.append("\n".join(line for i, line in enumerate(lines) if i not in drop))
    return cleaned

def _extract_pdf(file_path: str, doc_id: str, name: str) -> List[ExtractedContent]:
    """
    Extrae PDFs por página como Markdown (títulos, listas y código) con
    pymupdf4llm, para que el chunking estructural pueda respetar la jerarquía.
    Si pymupdf4llm no está disponible, falla o pierde texto en una página,
    esa página se extrae como texto plano con PyMuPDF.
    """
    texts = []
    pdf_document = pymupdf.open(file_path)
    try:
        try:
            import pymupdf4llm
            try:
                # Los niveles de título se calculan una vez sobre todo el documento
                hdr_info = pymupdf4llm.IdentifyHeaders(pdf_document)
            except Exception:
                hdr_info = None
        except ImportError:
            pymupdf4llm = None
            logger.warning("pymupdf4llm no está instalado; se extrae texto plano sin estructura.")

        for page_num in range(len(pdf_document)):
            plain = pdf_document[page_num].get_text("text")
            text = None
            if pymupdf4llm is not None:
                try:
                    text = _page_markdown(pymupdf4llm, pdf_document, page_num, hdr_info)
                except Exception:
                    logger.warning("pymupdf4llm falló en la página %s; se usa texto plano.", page_num + 1)
            if text is not None and len(text.split()) < MIN_MARKDOWN_COVERAGE * len(plain.split()):
                logger.warning("pymupdf4llm omitió texto en la página %s; se usa texto plano.", page_num + 1)
                text = None
            texts.append(plain if text is None else text)
    finally:
        pdf_document.close()

    return [
        ExtractedContent(
            text=text,
            metadata=DocumentMetadata(document_id=doc_id, name=name, doc_type="pdf", source=file_path, page=page_num + 1),
        )
        for page_num, text in enumerate(_remove_repeated_lines(texts))
    ]

def _extract_txt_md(file_path: str, doc_id: str, name: str, doc_type: str) -> List[ExtractedContent]:
    """Lectura directa para archivos TXT y Markdown."""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    meta = DocumentMetadata(
        document_id=doc_id, name=name, doc_type=doc_type, source=file_path
    )
    return [ExtractedContent(text=text, metadata=meta)]

def ingest_document(file_path: str, document_name: Optional[str] = None) -> IngestionResponse:
    """
    Punto de entrada IA-02: Orquesta la extracción, validación y normalización del documento.
    Devuelve estrictamente un objeto Pydantic (IngestionResult o IngestionError).
    `document_name` permite conservar el nombre original cuando el archivo llega
    con un nombre temporal (p. ej. desde el servicio HTTP).
    """
    if not os.path.exists(file_path):
        return IngestionError(
            codigo="ARCHIVO_NO_ENCONTRADO",
            mensaje=f"El archivo {file_path} no existe o la ruta es inválida."
        )

    name = document_name or os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower().strip('.')
    doc_id = generate_document_id(file_path)

    # 1. Extracción según el formato
    try:
        if ext == "pdf":
            extracted_pages = _extract_pdf(file_path, doc_id, name)
        elif ext in ["txt", "md", "markdown"]:
            doc_type = "md" if ext.startswith("md") else "txt"
            extracted_pages = _extract_txt_md(file_path, doc_id, name, doc_type)
        else:
            return IngestionError(
                codigo="FORMATO_NO_SOPORTADO",
                mensaje=f"El formato '{ext}' no está soportado. Utilice PDF, TXT o MD."
            )
    except Exception as e:
        return IngestionError(
            codigo="ERROR_EXTRACCION",
            mensaje=f"Fallo crítico al extraer contenido: {str(e)}"
        )

    # Combinamos para validación de contenido a nivel de documento completo
    full_text = " ".join([page.text for page in extracted_pages])

    # 2. Validación: Documento vacío o extracción insuficiente
    if not validate_content_not_empty(full_text):
        return IngestionError(
            codigo="DOCUMENTO_VACIO_O_ILEGIBLE",
            mensaje="El documento no contiene texto suficiente, está vacío o la extracción falló."
        )

    # 3. Validación: Pertinencia Técnica
    if not validate_technical_relevance(full_text):
        return IngestionError(
            codigo="DOCUMENTO_NO_TECNICO",
            mensaje="El documento no contiene contenido técnico suficiente para ser procesado por NuevaMente."
        )

    # 4. Normalización final y preparación del resultado
    normalized_content = []
    for content in extracted_pages:
        norm_text = normalize_text(content.text)
        if norm_text: # Descartamos páginas que se hayan vaciado tras la normalización
            content.text = norm_text
            normalized_content.append(content)

    # 4.1 Enriquecimiento pedagógico (IA-02 reapertura)
    from dataia.ingestion.enrichment import enrich_document_metadata
    pedagogical_meta = enrich_document_metadata(doc_id, full_text)

    # 5. Salida Exitosa
    return IngestionResult(
        document_id=doc_id,
        content=normalized_content,
        pedagogical_metadata=pedagogical_meta
    )
