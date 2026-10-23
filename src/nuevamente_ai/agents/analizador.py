"""
Nodo 1: Analizador e Instruccional (Router & Analyzer).
Extrae los conceptos clave, calibra el prompt de sistema para el perfil y estima el tiempo de estudio.
"""

from typing import Any, Dict
from nuevamente_ai.state import EstadoPipelineAdaptacion
from nuevamente_ai.prompts.perfiles import obtener_prompt_sistema
from nuevamente_ai.prompts.formatos import obtener_instrucciones_formato
from nuevamente_ai.prompts.dominios import obtener_pautas_dominio


def nodo_analizador(state: EstadoPipelineAdaptacion) -> Dict[str, Any]:
    """
    Analiza los parámetros de entrada y los fragmentos contextuales para preparar la estrategia pedagógica.
    """
    perfil = state.get("perfil_destinatario", "Junior")
    formato = state.get("formato_salida", "Flashcards")
    titulo = state.get("documento_titulo", "Documento Técnico")
    fragmentos = state.get("fragmentos_relevantes", [])

    # Obtener prompt de sistema adaptado al perfil
    prompt_sistema = obtener_prompt_sistema(perfil)
    instrucciones_formato = obtener_instrucciones_formato(formato)

    # Pautas de exactitud del dominio detectado por Data/IA (spec IA-02c R5)
    pautas_dominio = obtener_pautas_dominio(state.get("dominio_documento"))
    prompt_combinado = f"{prompt_sistema}\n\n{pautas_dominio}\n\n{instrucciones_formato}"

    # Extracción heurística rápida de conceptos clave preliminares
    texto_total = " ".join([f.get("contenido", "") for f in fragmentos])
    if not texto_total:
        texto_total = state.get("documento_contenido", "")

    # Extraer conceptos clave de apoyo
    palabras = [p.strip(".,;:()[]{}") for p in texto_total.split() if len(p) > 4 and p[0].isupper()]
    conceptos_unicos = list(dict.fromkeys(palabras))[:6]
    if not conceptos_unicos:
        conceptos_unicos = [titulo, "Fundamentos", "Buenas Prácticas"]

    # Estimación de tiempo didáctico
    tiempo_estimado = 5
    if formato == "Quiz Interactivo":
        tiempo_estimado = 8
    elif formato == "Mapa Mental":
        tiempo_estimado = 6
    elif formato == "Guia Paso a Paso":
        tiempo_estimado = 15

    return {
        "prompt_sistema_calibrado": prompt_combinado,
        "conceptos_clave": conceptos_unicos,
        "tiempo_estimado_minutos": tiempo_estimado,
        "contador_intentos": 0,
        "status": "analisis_completado"
    }
