"""
Nodo 2: Redactor Pedagógico (Content Creator).
Invoca al LLM para transformar la documentación técnica en el formato didáctico estructurado.
"""

import os
from typing import Any, Dict
from langchain_core.messages import SystemMessage, HumanMessage
from nuevamente_ai.state import EstadoPipelineAdaptacion
from nuevamente_ai.config import obtener_llm_etapa
from nuevamente_ai.schemas import ESQUEMA_GENERACION_POR_FORMATO, PaqueteContenidoAdaptado
from nuevamente_ai.utils.mermaid import generar_mermaid_desde_arbol, mapa_generado_a_arbol
from dataia.common.budget import estimate_tokens
from dataia.common.providers import call_provider


def nodo_creador(state: EstadoPipelineAdaptacion) -> Dict[str, Any]:
    """
    Genera el contenido estructurado adaptado utilizando el LLM con salida estructurada.
    """
    prompt_sistema = state.get("prompt_sistema_calibrado", "")
    fragmentos = state.get("fragmentos_relevantes", [])
    texto_fuente = "\n---\n".join([f.get("contenido", "") for f in fragmentos])
    if not texto_fuente:
        texto_fuente = state.get("documento_contenido", "")

    titulo = state.get("documento_titulo", "Documento")
    perfil = state.get("perfil_destinatario", "Junior")
    formato = state.get("formato_salida", "Flashcards")
    nicho = state.get("nicho_sector", "General")
    observaciones_previas = state.get("critica_observaciones")

    # Orientación con la metadata pedagógica del documento (spec IA-06 R5)
    metadata = state.get("metadata_documento") or {}
    orientacion = ""
    if metadata.get("conceptos_clave"):
        orientacion += f"CONCEPTOS CLAVE DEL DOCUMENTO (cúbrelos en lo posible): {', '.join(metadata['conceptos_clave'])}\n"
    if metadata.get("resumen_ejecutivo"):
        orientacion += f"SÍNTESIS DEL DOCUMENTO (solo como orientación; los hechos salen del texto fuente): {metadata['resumen_ejecutivo']}\n"

    # Construir prompt de usuario
    instruccion_usuario = (
        f"DOCUMENTO DE ENTRADA: '{titulo}'\n"
        f"PERFIL DESTINATARIO: {perfil}\n"
        f"FORMATO PEDAGÓGICO: {formato}\n"
        f"NICHO / CONTEXTO: {nicho}\n"
        f"{orientacion}\n"
        f"TEXTO FUENTE EXTRAÍDO DEL DOCUMENTO:\n{texto_fuente}\n\n"
    )

    if observaciones_previas:
        instruccion_usuario += (
            f"⚠️ RETROALIMENTACIÓN DEL AGENTE CRÍTICO (Corrige las siguientes observaciones):\n"
            f"{observaciones_previas}\n\n"
        )

    instruccion_usuario += (
        f"⚠️ REQUERIMIENTO DE NICHO (CRÍTICO): Adapta todos los ejemplos, analogías y la introducción estrictamente al contexto de {nicho}.\n"
        f"⚠️ REGLA DE FIDELIDAD (ANTI-ALUCINACIÓN): Las analogías deben construirse ÚNICAMENTE sobre conceptos presentes en el TEXTO FUENTE. NO inventes características técnicas, reglas de negocio o afirmaciones fácticas que no estén explícitamente en el documento.\n"
        "⚠️ ORTOGRAFÍA: Redacta en español con ortografía completa (tildes, ñ y signos de apertura ¿ ¡), también en títulos y etiquetas.\n\n"
        "Genera el paquete con 'titulo', 'introduccion_contextualizada' e 'items' "
        "conforme a las directrices de formato, perfil y nicho."
    )
    # Un esquema por formato (spec IA-06 R6): el modelo no elige entre formatos
    esquema = ESQUEMA_GENERACION_POR_FORMATO.get(formato, PaqueteContenidoAdaptado)

    # Invocar LLM con salida tipada estructurada
    try:
        structured_llm, limiter = obtener_llm_etapa(
            "GENERACION", esquema, temperatura=0.3,
            prompt_tokens=estimate_tokens(prompt_sistema + instruccion_usuario),
        )
        mensajes = [SystemMessage(content=prompt_sistema), HumanMessage(content=instruccion_usuario)]
        resultado = call_provider(
            "GENERADOR", lambda: structured_llm.invoke(mensajes), estimate_tokens(prompt_sistema + instruccion_usuario), limiter
        )
        borrador_dict = convertir_mapa_mental(resultado.model_dump())
    except Exception as e:
        if os.getenv("IA_STRICT_PROVIDERS") == "1":
            raise
        # Fallback de contingencia determinista si las API Keys no están configuradas en pruebas locales
        borrador_dict = _generar_borrador_fallback(titulo, perfil, formato, texto_fuente)

    intentos = state.get("contador_intentos", 0) + 1

    return {
        "borrador_contenido": borrador_dict,
        "contador_intentos": intentos,
        "status": "borrador_generado"
    }


def convertir_mapa_mental(borrador: Dict[str, Any]) -> Dict[str, Any]:
    """
    Si el borrador es un mapa sin recursión (ramas → subtemas → detalles), lo
    convierte al contrato: árbol con ids y Mermaid generado desde ese árbol, de
    modo que ambos siempre coinciden (spec IA-06 R7). Otros formatos pasan igual.
    """
    items = borrador.get("items")
    if not isinstance(items, dict) or "ramas" not in items:
        return borrador
    arbol = mapa_generado_a_arbol(items["ramas"])
    borrador["items"] = {
        "nodo_central": items.get("nodo_central", ""),
        "descripcion_general": items.get("descripcion_general", ""),
        "arbol": arbol,
        "codigo_mermaid": generar_mermaid_desde_arbol(items.get("nodo_central", ""), arbol),
    }
    return borrador


AVISO_CONTINGENCIA ="Contenido de contingencia: el proveedor de IA no estuvo disponible. Revise el documento original."


def _generar_borrador_fallback(titulo: str, perfil: str, formato: str, texto: str) -> Dict[str, Any]:
    """
    Borrador determinista para pruebas aisladas sin conexión a la API (solo fuera
    del modo estricto). No afirma hechos: indica que es contenido de contingencia
    y no supone ningún dominio (spec IA-02c R5).
    """
    if formato == "Flashcards":
        items = [
            {
                "frente": f"¿Cuáles son los conceptos principales de '{titulo}'?",
                "dorso": AVISO_CONTINGENCIA,
                "pista_didactica": "Repasa los títulos y las definiciones del documento.",
                "categoria_dificultad": "Básico"
            },
            {
                "frente": f"¿Qué procedimientos o reglas describe '{titulo}'?",
                "dorso": AVISO_CONTINGENCIA,
                "pista_didactica": "Busca las listas de pasos y las condiciones del documento.",
                "categoria_dificultad": "Intermedio"
            }
        ]
    elif formato == "Quiz Interactivo":
        items = [
            {
                "pregunta": f"¿Dónde se encuentra la información sobre '{titulo}'?",
                "opciones": [
                    "En una fuente externa no relacionada",
                    "En el documento original",
                    "En ninguna fuente",
                    "En una suposición propia"
                ],
                "indice_correcto": 1,
                "justificacion_tecnica": AVISO_CONTINGENCIA,
                "pista_didactica": "La fuente de verdad es el documento cargado.",
                "explicacion_distractores": "Solo el documento original respalda el contenido."
            }
        ]
    elif formato == "Mapa Mental":
        items = {
            "nodo_central": titulo,
            "descripcion_general": AVISO_CONTINGENCIA,
            "arbol": [
                {"id": "n1", "etiqueta": "Conceptos principales", "subnodos": []},
                {"id": "n2", "etiqueta": "Procedimientos y reglas", "subnodos": []},
                {"id": "n3", "etiqueta": "Aplicación práctica", "subnodos": []}
            ],
            "codigo_mermaid": f"mindmap\n  root(({titulo}))\n    Conceptos principales\n    Procedimientos y reglas\n    Aplicación práctica"
        }
    else:
        items = {
            "tldr": AVISO_CONTINGENCIA,
            "puntos_clave": ["Conceptos principales del documento", "Procedimientos y reglas", "Aplicación práctica"],
            "impacto_negocio": AVISO_CONTINGENCIA,
            "recomendaciones": ["Revisar el documento original", "Reintentar la generación más tarde"]
        }

    return {
        "titulo": f"{titulo} ({perfil})",
        "introduccion_contextualizada": AVISO_CONTINGENCIA,
        "items": items
    }
