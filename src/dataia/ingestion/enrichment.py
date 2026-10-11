import os
import json
import logging
from dataia.common.credentials import get_gemini_model, get_google_api_key
from dataia.common.models import DocumentPedagogicalMetadata
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# El document_id deriva del contenido, por lo que la caché es reutilizable entre ingestiones
CACHE_DIR = os.path.join(os.getenv("DATAIA_CACHE_DIR", ".dataia_cache"), "metadata")

def enrich_document_metadata(document_id: str, full_text: str) -> DocumentPedagogicalMetadata:
    """
    Genera la metadata pedagógica del documento con Gemini (modelo de GEMINI_MODEL).
    Guarda el resultado en `DATAIA_CACHE_DIR/metadata/{document_id}.json`.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{document_id}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DocumentPedagogicalMetadata(**data)
        except Exception:
            pass # Fallback to re-generating

    try:
        llm = ChatGoogleGenerativeAI(model=get_gemini_model(), temperature=0.0, google_api_key=get_google_api_key())
        structured_llm = llm.with_structured_output(DocumentPedagogicalMetadata)
        
        prompt = (
            "Extrae la metadata pedagógica del siguiente documento técnico.\n"
            f"El ID del documento es: {document_id}\n\n"
            f"Documento:\n{full_text[:4000000]}\n" # Limiting slightly to avoid exceeding 1M tokens just in case, but 5MB is well within 1M tokens.
        )
        
        result = structured_llm.invoke(prompt)
        
        # Ensure document_id is correct
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
