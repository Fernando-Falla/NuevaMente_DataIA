import re

def normalize_text(text: str) -> str:
    """
    Normaliza el texto extraído sin perder la información técnica o la estructura general.
    """
    if not text:
        return ""
        
    # Eliminar caracteres nulos
    text = text.replace("\x00", "")
    
    # Normalizar múltiples espacios horizontales a uno solo (preservando saltos de línea)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Normalizar más de 3 saltos de línea consecutivos a 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
