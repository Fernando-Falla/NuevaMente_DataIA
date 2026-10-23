"""
Fábrica agnóstica de LLMs para NuevaMente AI Core.
Soporta Google Gemini (vía langchain-google-genai) con failover automático a Groq Cloud.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from dataia.common.providers import create_gemini_llm, provider_limits

try:
    # Habilitar caché global en memoria para ahorrar tokens
    from langchain.globals import set_llm_cache
    from langchain_community.cache import InMemoryCache
    set_llm_cache(InMemoryCache())
except ImportError:
    # Silently pass if langchain globals or community packages are missing (Fallback for environments without them)
    pass


def obtener_llm_adaptacion(temperatura: float = 0.3, provider_override: Optional[str] = None):
    """
    Retorna una instancia de LLM lista para invocar, configurada según variables de entorno.
    Si Gemini falla o la cuota se agota (HTTP 429), permite conmutar a Groq Cloud.
    """
    provider = provider_override or os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY no encontrada en el entorno.")
        from langchain_groq import ChatGroq
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=temperatura,
            max_retries=provider_limits()[1],
            timeout=provider_limits()[0],
        )

    # Proveedor primario: Google Gemini
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no encontrada en el entorno. Configure .env")

    gemini_llm = create_gemini_llm(temperatura)
    
    # Failover automatico a Groq si falla Gemini
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        try:
            from langchain_groq import ChatGroq
            groq_llm = ChatGroq(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                api_key=groq_api_key,
                temperature=temperatura,
                max_retries=provider_limits()[1],
                timeout=provider_limits()[0],
            )
            return gemini_llm.with_fallbacks([groq_llm])
        except ImportError:
            pass

    return gemini_llm


def obtener_llm_critico():
    """Retorna un modelo determinista (temperatura=0.0) para el Agente Crítico de Calidad."""
    return obtener_llm_adaptacion(temperatura=0.0)
