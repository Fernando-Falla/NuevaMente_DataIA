import os
import json
import logging
import re
from typing import List

from dataia.common.budget import doc_metadata_max_tokens, estimate_tokens
from dataia.common.credentials import get_google_api_key
from dataia.common.models import DocumentPedagogicalMetadata, ExtractedContent
from dataia.common.providers import call_provider, create_stage_llm

logger = logging.getLogger(__name__)

# El document_id deriva del contenido, por lo que la caché es reutilizable entre ingestiones
CACHE_DIR = os.path.join(os.getenv("DATAIA_CACHE_DIR", ".dataia_cache"), "metadata")

_HEADER = re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE)


def build_document_digest(contents: List[ExtractedContent], max_tokens: int | None = None) -> str:
    """
    Resumen acotado del documento para la llamada de metadata (spec IA-02b R2):
    la lista de títulos y el inicio de cada sección, sin superar max_tokens.
    Un documento que ya cabe en el presupuesto se envía completo.
    """
    max_tokens = max_tokens or doc_metadata_max_tokens()
    full_text = "\n\n".join(c.text for c in contents)
    if estimate_tokens(full_text) <= max_tokens:
        return full_text

    headers = list(dict.fromkeys(m.group(0).strip() for m in _HEADER.finditer(full_text)))
    outline = "ESTRUCTURA DEL DOCUMENTO:\n" + "\n".join(headers)
    # La estructura ocupa como máximo un cuarto del presupuesto
    while headers and estimate_tokens(outline) > max_tokens // 4:
        headers = headers[: len(headers) * 3 // 4]
        outline = "ESTRUCTURA DEL DOCUMENTO (parcial):\n" + "\n".join(headers)

    # Secciones: el texto entre títulos; sin títulos, cada página es una sección
    sections = [s for s in re.split(r"(?=^#{1,6}[ \t]+\S)", full_text, flags=re.MULTILINE) if s.strip()]
    if len(sections) <= 1:
        sections = [c.text for c in contents if c.text.strip()]
    remaining = max_tokens - estimate_tokens(outline)
    per_section_words = max(30, int(remaining / 1.3 / max(len(sections), 1)))

    extracts = []
    for section in sections:
        words = section.split()
        extract = " ".join(words[:per_section_words])
        if estimate_tokens("\n\n".join(extracts + [extract])) > remaining:
            break
        extracts.append(extract)
    return outline + "\n\nEXTRACTOS DE CADA SECCIÓN:\n\n" + "\n\n".join(extracts)


def enrich_document_metadata(document_id: str, document_digest: str) -> DocumentPedagogicalMetadata:
    """
    Genera la metadata pedagógica y el dominio del documento con Gemini a partir
    de su resumen acotado (build_document_digest).
    Guarda el resultado en `DATAIA_CACHE_DIR/metadata/{document_id}.json`.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{document_id}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = DocumentPedagogicalMetadata(**json.load(f))
            # Las entradas anteriores a la detección de dominio se regeneran
            if cached.dominio is not None:
                return cached
        except Exception:
            pass

    try:
        prompt = (
            "Extrae la metadata pedagógica del siguiente documento y clasifica su dominio.\n"
            "Dominios: 'TI' (software, redes, nube, datos, ciberseguridad), 'Fintech' (pagos, banca digital, "
            "finanzas, regulación financiera), 'Salud' (clínica, farmacología, procedimientos y normas sanitarias), "
            "'Marketing digital' (campañas, SEO/SEM, analítica, redes sociales, embudos de conversión) u 'Otro'.\n"
            "es_documento_tecnico es True si es material técnico o profesional de su dominio (manual, guía, norma, "
            "protocolo, documentación) y False si es divulgación general, ficción, recetas o contenido personal.\n"
            f"El ID del documento es: {document_id}\n\n"
            f"Documento:\n{document_digest}\n"
        )
        structured_llm, limiter = create_stage_llm(
            "CLASIFICACION", DocumentPedagogicalMetadata, gemini_api_key=get_google_api_key(), prompt_tokens=estimate_tokens(prompt)
        )

        result = call_provider("ENRIQUECIMIENTO_DOCUMENTO", lambda: structured_llm.invoke(prompt), estimate_tokens(prompt), limiter)
        if result is None:
            raise ValueError("El LLM no devolvió metadata válida.")

        result.document_id = document_id

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        return result
    except Exception as e:
        if os.getenv("IA_STRICT_PROVIDERS") == "1":
            raise
        logger.warning("Metadata pedagógica del documento no disponible; se usan valores vacíos (%s: %s)", type(e).__name__, str(e)[:200])
        return DocumentPedagogicalMetadata(
            document_id=document_id,
            conceptos_clave=[],
            prerequisitos=[],
            resumen_ejecutivo="No se pudo extraer el resumen.",
            nicho_sugerido="General"
        )
