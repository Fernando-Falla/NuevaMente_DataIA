"""
Definición y compilación del grafo de LangGraph para NuevaMente AI Core.
"""

from langgraph.graph import StateGraph, START, END
from nuevamente_ai.state import EstadoPipelineAdaptacion
from nuevamente_ai.agents.analizador import nodo_analizador
from nuevamente_ai.agents.creador import nodo_creador
from nuevamente_ai.agents.critico import nodo_critico, decidir_proximo_paso
from nuevamente_ai.agents.ensamblador import nodo_ensamblador


def compilar_grafo_adaptacion():
    """
    Construye y compila el flujo de decisión de los agentes de IA.
    """
    builder = StateGraph(EstadoPipelineAdaptacion)

    # Registro de nodos
    builder.add_node("nodo_analizador", nodo_analizador)
    builder.add_node("nodo_creador", nodo_creador)
    builder.add_node("nodo_critico", nodo_critico)
    builder.add_node("nodo_ensamblador", nodo_ensamblador)

    # Transiciones
    builder.add_edge(START, "nodo_analizador")
    builder.add_edge("nodo_analizador", "nodo_creador")
    builder.add_edge("nodo_creador", "nodo_critico")

    # Bucle de reintento del Agente Crítico
    builder.add_conditional_edges(
        "nodo_critico",
        decidir_proximo_paso,
        {
            "nodo_creador": "nodo_creador",
            "nodo_ensamblador": "nodo_ensamblador"
        }
    )

    builder.add_edge("nodo_ensamblador", END)

    return builder.compile()


# Instancia compilada global reutilizable
grafo_adaptacion_compilado = compilar_grafo_adaptacion()
