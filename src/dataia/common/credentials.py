import os
from typing import Optional

# Modelo para la metadata pedagógica (documento y chunks). Google retira modelos
# para las claves nuevas (gemini-2.5-flash responde 404): se cambia con
# GEMINI_MODEL sin tocar el código.
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

def get_google_api_key() -> Optional[str]:
    """
    Clave de Gemini para los módulos Data/IA (ingestión, chunking y vector store).
    DATAIA_GOOGLE_API_KEY permite que estas etapas consuman una cuota propia,
    separada de la que usa AI Core; si no está definida, se usa GOOGLE_API_KEY.
    """
    return os.getenv("DATAIA_GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") or None

def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
