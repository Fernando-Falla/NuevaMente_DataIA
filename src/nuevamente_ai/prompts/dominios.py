"""
Pautas de exactitud por dominio del documento (spec IA-02c R6).
El dominio lo detecta Data/IA; el nicho (sector de los ejemplos) lo elige el usuario.
"""

PAUTAS_POR_DOMINIO = {
    "TI": (
        "DOMINIO DEL DOCUMENTO: TI.\n"
        "- Reproduce comandos, fragmentos de código, versiones, puertos y nombres de configuración exactamente como en la fuente.\n"
        "- No inventes parámetros, valores por defecto ni compatibilidades que la fuente no mencione."
    ),
    "Fintech": (
        "DOMINIO DEL DOCUMENTO: FINTECH.\n"
        "- Reproduce cifras, tasas, comisiones, plazos y nombres de normas exactamente como en la fuente.\n"
        "- No emitas recomendaciones de inversión ni asesoría financiera personal."
    ),
    "Salud": (
        "DOMINIO DEL DOCUMENTO: SALUD.\n"
        "- Reproduce dosis, unidades, umbrales y criterios clínicos exactamente como en la fuente; nunca los redondees ni los extrapoles.\n"
        "- No des consejo médico personal. Indica en la introducción que es material educativo y no sustituye el criterio de un profesional de la salud."
    ),
    "Marketing digital": (
        "DOMINIO DEL DOCUMENTO: MARKETING DIGITAL.\n"
        "- Usa las métricas y fórmulas (CTR, CPC, CPA, ROAS, tasa de conversión…) tal como las define la fuente.\n"
        "- No prometas resultados ni cifras de rendimiento que la fuente no respalde."
    ),
}

PAUTA_GENERAL = (
    "DOMINIO DEL DOCUMENTO: no identificado.\n"
    "- Reproduce cifras, nombres propios y términos técnicos exactamente como en la fuente."
)


def obtener_pautas_dominio(dominio: str | None) -> str:
    return PAUTAS_POR_DOMINIO.get(dominio or "", PAUTA_GENERAL)
