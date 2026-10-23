import re
import unicodedata
from typing import Dict, List, Optional, Tuple

def validate_content_not_empty(text: str) -> bool:
    """
    Valida que el contenido extraído tenga una longitud razonable y no esté vacío.
    """
    if not text or len(text.strip()) < 50:
        return False
    return True

# Léxico de respaldo por dominio (spec IA-02c R3). Se usa cuando el LLM no
# clasifica el dominio. Términos sin acentos y en minúsculas; se admiten plurales.
DOMAIN_LEXICON: Dict[str, List[str]] = {
    "TI": [
        "api", "endpoint", "servidor", "base de datos", "sql", "kubernetes", "docker", "contenedor", "pod",
        "deployment", "despliegue", "microservicio", "nube", "cloud", "backend", "frontend", "codigo fuente",
        "algoritmo", "compilador", "sistema operativo", "http", "tcp", "dns", "subred", "firewall", "cifrado",
        "autenticacion", "jwt", "token", "cluster", "repositorio", "git", "python", "java", "javascript",
        "linux", "latencia", "ciberseguridad", "vcn", "oci", "software",
    ],
    "Fintech": [
        "pago", "tarjeta", "transaccion", "conciliacion", "adquirente", "emisor", "liquidacion", "comision",
        "tasa de interes", "tasa de intercambio", "credito", "prestamo", "cuenta bancaria", "banca", "banco",
        "billetera digital", "transferencia", "swift", "iban", "kyc", "aml", "lavado de activos", "pci dss",
        "fraude", "criptomoneda", "blockchain", "fintech", "open banking", "cobro", "factura", "fondos",
        "comercio", "autorizacion", "regulacion financiera",
    ],
    "Salud": [
        "paciente", "diagnostico", "tratamiento", "dosis", "farmaco", "medicamento", "terapia", "sintoma",
        "clinico", "clinica", "hospital", "enfermeria", "presion arterial", "glucosa", "insulina", "hipertension",
        "diabetes", "mmhg", "posologia", "contraindicacion", "efecto adverso", "historia clinica",
        "epidemiologia", "vacuna", "infeccion", "cirugia", "triaje", "signos vitales", "creatinina", "diuretico",
        "potasio", "ieca",
    ],
    "Marketing digital": [
        "campana", "seo", "sem", "ppc", "cpc", "cpa", "ctr", "roas", "conversion", "embudo", "lead", "audiencia",
        "segmentacion", "palabra clave", "puja", "anuncio", "publicidad", "publicitaria", "impresion", "clic",
        "engagement", "redes sociales", "influencer", "email marketing", "landing page", "trafico organico",
        "posicionamiento", "branding", "remarketing", "retargeting", "kpi", "analitica web", "google ads",
        "costo por adquisicion",
    ],
}
MIN_DOMAIN_MATCHES = 3

def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))

_DOMAIN_PATTERNS = {
    domain: [(term, re.compile(r"\b" + re.escape(term) + r"(?:es|s)?\b")) for term in terms]
    for domain, terms in DOMAIN_LEXICON.items()
}

def detect_domain_by_lexicon(text: str) -> Tuple[Optional[str], Dict[str, List[str]]]:
    """
    Devuelve el dominio con más términos distintos (al menos MIN_DOMAIN_MATCHES)
    o None si ninguno alcanza el mínimo, junto con los términos encontrados.
    """
    normalized = _normalize(text)
    found = {domain: [term for term, pattern in patterns if pattern.search(normalized)] for domain, patterns in _DOMAIN_PATTERNS.items()}
    best = max(found, key=lambda d: len(found[d]))
    return (best if len(found[best]) >= MIN_DOMAIN_MATCHES else None), found
