import re

def validate_content_not_empty(text: str) -> bool:
    """
    Valida que el contenido extraído tenga una longitud razonable y no esté vacío.
    """
    if not text or len(text.strip()) < 50:
        return False
    return True

def validate_technical_relevance(text: str) -> bool:
    """
    Validación heurística y determinista (100% local) para pertinencia técnica del MVP.
    Identifica si el documento contiene un umbral mínimo de términos técnicos.
    """
    tech_keywords = [
        "arquitectura", "código", "sistema", "red", "api", "servidor", 
        "nube", "cloud", "jwt", "vcn", "microservicios", "token", "datos", 
        "software", "hardware", "protocolo", "seguridad", "oci", "oracle",
        "infraestructura", "endpoint", "base de datos", "backend", "frontend"
    ]
    text_lower = text.lower()
    
    # Contamos cuántas palabras clave únicas técnicas aparecen
    matches = sum(1 for kw in tech_keywords if kw in text_lower)
    
    # Se aprueba si tiene al menos menciones a 3 conceptos técnicos distintos
    return matches >= 3
