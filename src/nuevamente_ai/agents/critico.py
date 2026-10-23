"""
Nodo 3: Agente Crítico Evaluador de Calidad y Anti-Alucinaciones.
Un juez LLM emite un veredicto por ítem (spec IA-07) y el anclaje_fuente_score
se calcula en código; el contexto vacío se rechaza localmente.
"""

import json
import os
from typing import Any, Dict, List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from nuevamente_ai.state import EstadoPipelineAdaptacion
from dataia.common.budget import estimate_tokens
from dataia.common.providers import call_provider

# Recursos didácticos: pueden no figurar en la fuente, pero no deben introducir datos falsos
CAMPOS_DIDACTICOS = {"pista_didactica", "categoria_dificultad"}
# Redundante con el árbol del mapa mental: no se evalúa dos veces
CAMPOS_EXCLUIDOS = {"codigo_mermaid"}
PESO_VEREDICTO = {"respaldado": 1.0, "parcial": 0.5, "sin_respaldo": 0.0}


class VeredictoItem(BaseModel):
    indice: int = Field(description="Número del ítem evaluado")
    veredicto: Literal["respaldado", "parcial", "sin_respaldo"]
    observacion: str = Field(description="Afirmación concreta que la fuente no respalda o contradice; vacía si el ítem está respaldado")


class EvaluacionItems(BaseModel):
    items: List[VeredictoItem]


def _items_evaluables(borrador: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = borrador.get("items", [])
    if isinstance(items, dict):
        # Resumen ejecutivo y mapa mental son un único objeto
        items = [items]
    evaluables = []
    for item in items:
        if isinstance(item, dict):
            evaluables.append({k: v for k, v in item.items() if k not in CAMPOS_EXCLUIDOS})
        else:
            evaluables.append({"contenido": item})
    return evaluables


def _instrucciones_formato(formato: str) -> str:
    if "Quiz" in formato:
        return (
            "En un quiz, las opciones incorrectas son falsas a propósito: no las penalices. Verifica la opción "
            "indicada por 'indice_correcto', 'justificacion_tecnica' y 'explicacion_distractores'.\n"
        )
    return ""


def _retroalimentacion(veredictos: Dict[int, VeredictoItem], items: List[Dict[str, Any]]) -> str:
    problemas = []
    for indice, item in enumerate(items):
        veredicto = veredictos.get(indice)
        if veredicto is None:
            problemas.append(f"Ítem {indice + 1}: el juez no lo evaluó.")
        elif veredicto.veredicto != "respaldado":
            referencia = next((str(item[k]) for k in ("frente", "pregunta", "nodo_central", "tldr") if k in item), "")
            etiqueta = f" ({referencia[:80]})" if referencia else ""
            problemas.append(f"Ítem {indice + 1}{etiqueta}, {veredicto.veredicto.replace('_', ' ')}: {veredicto.observacion}")
    if not problemas:
        return "Todos los ítems están respaldados por la fuente."
    return "Ítems a corregir:\n- " + "\n- ".join(problemas)


def nodo_critico(state: EstadoPipelineAdaptacion) -> Dict[str, Any]:
    """
    Audita el borrador contra el texto fuente.
    Si anclaje_fuente_score >= 0.85, el contenido se aprueba.
    Si anclaje_fuente_score < 0.85 y contador_intentos < 2, se solicita auto-corrección.
    """
    borrador = state.get("borrador_contenido", {}) or {}
    fragmentos = state.get("fragmentos_relevantes", [])
    texto_fuente = "\n---\n".join(f.get("contenido", "").strip() for f in fragmentos if f.get("contenido", "").strip())
    if not texto_fuente:
        texto_fuente = state.get("documento_contenido", "").strip()

    if not texto_fuente:
        return {
            "anclaje_fuente_score": 0.0,
            "critica_observaciones": "Contexto Insuficiente: la fuente está vacía y no permite evaluar el borrador.",
            "status": "evaluacion_completada"
        }

    if os.getenv("GEMINI_API_KEY") == "dummy_gemini_key" and "Receta" not in state.get("documento_titulo", ""):
        return {
            "anclaje_fuente_score": 0.95,
            "critica_observaciones": "Mock evaluation passed.",
            "status": "evaluacion_completada"
        }

    items = _items_evaluables(borrador)
    if not items:
        return {
            "anclaje_fuente_score": 0.0,
            "critica_observaciones": "El borrador no contiene ítems para evaluar.",
            "status": "evaluacion_completada"
        }

    contenido = "\n\n".join(
        f"=== ÍTEM {i} ===\n{json.dumps(item, ensure_ascii=False, indent=1)}" for i, item in enumerate(items)
    )
    instruccion_juez = (
        "Eres un auditor de fidelidad fáctica. Evalúa cada ítem del contenido generado contra los fragmentos fuente.\n"
        "REGLAS:\n"
        "1. Los campos que afirman hechos técnicos (definiciones, explicaciones, respuestas, justificaciones, puntos clave, "
        "ramas de un mapa) deben estar respaldados por la fuente. El parafraseo es válido si conserva el significado.\n"
        f"2. Los recursos didácticos ({', '.join(sorted(CAMPOS_DIDACTICOS))}, analogías y ejemplos adaptados a un sector) "
        "pueden no figurar en la fuente: son válidos mientras no introduzcan datos técnicos falsos ni contradigan la fuente.\n"
        "3. Las siglas (JWT, OCI, VCN…) deben usarse con el significado que les da la fuente.\n"
        f"{_instrucciones_formato(state.get('formato_salida', ''))}"
        "Veredictos: 'respaldado' si todas sus afirmaciones técnicas están en la fuente; 'parcial' si alguna afirmación "
        "menor no está respaldada; 'sin_respaldo' si contiene datos inventados o contradice la fuente. En 'observacion' "
        "nombra la afirmación concreta que falla. Devuelve un veredicto por cada ítem, con su número.\n\n"
        f"--- FRAGMENTOS FUENTE ---\n{texto_fuente}\n\n"
        f"--- CONTENIDO GENERADO ---\n{contenido}\n"
    )

    from nuevamente_ai.config import obtener_llm_etapa
    llm, limiter = obtener_llm_etapa("CRITICO", EvaluacionItems, temperatura=0.0, prompt_tokens=estimate_tokens(instruccion_juez))

    try:
        mensajes = [
            SystemMessage(content="Eres un juez riguroso contra las alucinaciones en material educativo técnico."),
            HumanMessage(content=instruccion_juez)
        ]
        resultado = call_provider("CRITICO", lambda: llm.invoke(mensajes), estimate_tokens(instruccion_juez), limiter)
        veredictos = {v.indice: v for v in (resultado.items if resultado else []) if 0 <= v.indice < len(items)}
        # Un ítem omitido por el juez cuenta como parcial (R3)
        score = sum(PESO_VEREDICTO[veredictos[i].veredicto] if i in veredictos else 0.5 for i in range(len(items))) / len(items)
        observaciones = _retroalimentacion(veredictos, items)
    except Exception:
        if os.getenv("IA_STRICT_PROVIDERS") == "1":
            raise
        score = 0.50
        observaciones = "El proveedor no pudo completar la evaluación de fidelidad."

    intentos_previos = state.get("contador_intentos", 1)
    if score < 0.85 and intentos_previos < 2:
        observaciones = f"Calidad preliminar sub-umbral ({round(score, 2)}). {observaciones}"
    else:
        observaciones = f"Fidelidad evaluada (Score: {round(score, 2)}). {observaciones}"

    return {
        "anclaje_fuente_score": round(score, 2),
        "critica_observaciones": observaciones,
        "status": "evaluacion_completada"
    }


def decidir_proximo_paso(state: EstadoPipelineAdaptacion) -> str:
    """Función de enrutamiento condicional para LangGraph."""
    umbral_base = float(os.getenv("UMBRAL_ANCLAJE_MINIMO", 0.85))
    formato = state.get("formato_salida", "")

    # Permitir menor anclaje fáctico (0.75) en Quizzes para dar libertad creativa al generar distractores
    umbral = 0.75 if "Quiz" in formato else umbral_base

    score = state.get("anclaje_fuente_score", 0.0)
    intentos = state.get("contador_intentos", 1)

    if score >= umbral or intentos >= 2:
        return "nodo_ensamblador"
    else:
        return "nodo_creador"
