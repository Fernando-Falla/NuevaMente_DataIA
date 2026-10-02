import os
import uuid
from typing import List, Union
import pymupdf

from dataia.common.models import (
    DocumentMetadata, ExtractedContent, IngestionResult, IngestionError, IngestionResponse
)
from dataia.ingestion.validators import validate_content_not_empty, validate_technical_relevance
from dataia.ingestion.normalizer import normalize_text

def generate_document_id() -> str:
    """Genera el identificador único requerido para la trazabilidad del pipeline."""
    return f"doc-{uuid.uuid4().hex[:8]}"

def _extract_pdf(file_path: str, doc_id: str, name: str) -> List[ExtractedContent]:
    """Extrae texto de PDFs por página utilizando PyMuPDF."""
    results = []
    pdf_document = pymupdf.open(file_path)
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        text = page.get_text("text")
        meta = DocumentMetadata(
            document_id=doc_id, name=name, doc_type="pdf", source=file_path, page=page_num + 1
        )
        results.append(ExtractedContent(text=text, metadata=meta))
    return results

def _extract_txt_md(file_path: str, doc_id: str, name: str, doc_type: str) -> List[ExtractedContent]:
    """Lectura directa para archivos TXT y Markdown."""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    meta = DocumentMetadata(
        document_id=doc_id, name=name, doc_type=doc_type, source=file_path
    )
    return [ExtractedContent(text=text, metadata=meta)]

def ingest_document(file_path: str) -> IngestionResponse:
    """
    Punto de entrada IA-02: Orquesta la extracción, validación y normalización del documento.
    Devuelve estrictamente un objeto Pydantic (IngestionResult o IngestionError).
    """
    if not os.path.exists(file_path):
        return IngestionError(
            codigo="ARCHIVO_NO_ENCONTRADO",
            mensaje=f"El archivo {file_path} no existe o la ruta es inválida."
        )

    name = os.path.basename(file_path)
    ext = os.path.splitext(name)[1].lower().strip('.')
    doc_id = generate_document_id()

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
