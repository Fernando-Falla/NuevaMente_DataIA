import os
import json
from dataia.common.models import DocumentPedagogicalMetadata
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

CACHE_DIR = ".dataia_cache/metadata"

def enrich_document_metadata(document_id: str, full_text: str) -> DocumentPedagogicalMetadata:
    """
    Generates pedagogical metadata using Gemini 2.5 Flash.
    Caches the result in `.dataia_cache/metadata/{document_id}.json`.
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
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
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
        return DocumentPedagogicalMetadata(
            document_id=document_id,
            conceptos_clave=[],
            prerequisitos=[],
            resumen_ejecutivo="No se pudo extraer el resumen.",
            nicho_sugerido="General"
        )
