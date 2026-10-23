"""
Nodo 2: Redactor Pedagógico (Content Creator).
Invoca al LLM para transformar la documentación técnica en el formato didáctico estructurado.
"""

import os
from typing import Any, Dict
from langchain_core.messages import SystemMessage, HumanMessage
from nuevamente_ai.state import EstadoPipelineAdaptacion
from nuevamente_ai.config import obtener_llm_adaptacion
from nuevamente_ai.schemas import PaqueteContenidoAdaptado
from dataia.common.providers import provider_call


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

    # Construir prompt de usuario
    instruccion_usuario = (
        f"DOCUMENTO DE ENTRADA: '{titulo}'\n"
        f"PERFIL DESTINATARIO: {perfil}\n"
        f"FORMATO PEDAGÓGICO: {formato}\n"
        f"NICHO / CONTEXTO: {nicho}\n\n"
        f"TEXTO FUENTE EXTRAÍDO DEL DOCUMENTO:\n{texto_fuente}\n\n"
    )

    if observaciones_previas:
        instruccion_usuario += (
            f"⚠️ RETROALIMENTACIÓN DEL AGENTE CRÍTICO (Corrige las siguientes observaciones):\n"
            f"{observaciones_previas}\n\n"
        )

    instruccion_usuario += (
        f"⚠️ REQUERIMIENTO DE NICHO (CRÍTICO): Adapta todos los ejemplos, analogías y la introducción estrictamente al contexto de {nicho}.\n"
        f"⚠️ REGLA DE FIDELIDAD (ANTI-ALUCINACIÓN): Las analogías deben construirse ÚNICAMENTE sobre conceptos presentes en el TEXTO FUENTE. NO inventes características técnicas, reglas de negocio o afirmaciones fácticas que no estén explícitamente en el documento.\n\n"
        "Genera un objeto PaqueteContenidoAdaptado con 'titulo', 'introduccion_contextualizada' e 'items' "
        "conforme a las directrices de formato, perfil y nicho."
    )

    # Invocar LLM con salida tipada estructurada
    try:
        llm = obtener_llm_adaptacion(temperatura=0.3)
        structured_llm = llm.with_structured_output(PaqueteContenidoAdaptado)
        with provider_call("GENERADOR"):
            resultado: PaqueteContenidoAdaptado = structured_llm.invoke([
                SystemMessage(content=prompt_sistema),
                HumanMessage(content=instruccion_usuario)
            ])
        borrador_dict = resultado.model_dump()
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


def _generar_borrador_fallback(titulo: str, perfil: str, formato: str, texto: str) -> Dict[str, Any]:
    """Genera un borrador determinista basado en heurísticas para pruebas aisladas sin conexión a API."""
    if formato == "Flashcards":
        items = [
            {
                "frente": f"¿Qué principio fundamental describe '{titulo}'?",
                "dorso": f"Explica la arquitectura y fundamentos de {titulo} para el perfil {perfil}.",
                "pista_didactica": "Piensa en el funcionamiento modular de un sistema distribuido.",
                "categoria_dificultad": "Básico"
            },
            {
                "frente": "¿Cuál es la función operativa principal del componente analizado?",
                "dorso": "Regula la comunicación, seguridad y persistencia de las cargas de trabajo técnicas.",
                "pista_didactica": "Es como un guardia perimetral de seguridad.",
                "categoria_dificultad": "Intermedio"
            }
        ]
    elif formato == "Quiz Interactivo":
        items = [
            {
                "pregunta": f"Respecto a {titulo}, ¿cuál es la mejor práctica recomendada?",
                "opciones": [
                    "Ignorar los mecanismos de aislamiento y seguridad",
                    "Configurar segmentación de red y políticas de acceso mínimo",
                    "Desactivar las alertas presupuestarias de costos",
                    "Ejecutar todos los servicios en un solo puerto sin cifrado"
                ],
                "indice_correcto": 1,
                "justificacion_tecnica": "El principio de mínimo privilegio y la segmentación previenen accesos no autorizados.",
                "pista_didactica": "Aplica el principio de defensa en profundidad.",
                "explicacion_distractores": "Las otras alternativas violan las buenas prácticas de seguridad y control de costos."
            }
        ]
    elif formato == "Mapa Mental":
        items = {
            "nodo_central": titulo,
            "descripcion_general": f"Estructura jerárquica de {titulo} para nivel {perfil}",
            "arbol": [
                {"id": "n1", "etiqueta": "Arquitectura y Fundamentos", "subnodos": []},
                {"id": "n2", "etiqueta": "Seguridad y Políticas", "subnodos": []},
                {"id": "n3", "etiqueta": "Operación y Buenas Prácticas", "subnodos": []}
            ],
            "codigo_mermaid": f"mindmap\n  root(({titulo}))\n    Arquitectura\n      Fundamentos\n      Componentes\n    Seguridad\n      Políticas\n      Reglas de Red\n    Operaciones\n      Monitoreo\n      Costos"
        }
    else:
        items = {
            "tldr": f"Síntesis ejecutiva de {titulo} orientada a perfil {perfil}.",
            "puntos_clave": ["Eficiencia de costos", "Escalabilidad modular", "Cumplimiento normativo"],
            "impacto_negocio": "Reduce el tiempo de adopción técnica y optimiza el ROI.",
            "recomendaciones": ["Iniciar despliegue en ambiente de prueba", "Verificar alertas de presupuesto"]
        }

    return {
        "titulo": f"{titulo} ({perfil})",
        "introduccion_contextualizada": f"Material adaptado didácticamente para {perfil}.",
        "items": items
    }
