"""
Instrucciones especializadas y plantillas Few-Shot según el formato didáctico solicitado.
"""

from nuevamente_ai.schemas import FormatoSalidaEnum

INSTRUCCIONES_FORMATOS = {
    FormatoSalidaEnum.FLASHCARDS: (
        "FORMATO SOLICITADO: FLASHCARDS INTERACTIVAS (Tarjetas de Memorización Activa).\n"
        "Debes generar una colección de entre 4 y 8 tarjetas estructuradas.\n"
        "Para cada tarjeta incluye:\n"
        "- frente: Pregunta directa o concepto nuclear.\n"
        "- dorso: Explicación pedagógica clara y rigurosa basada en el texto.\n"
        "- pista_didactica: Analogía o truco mnemotécnico para facilitar la retención.\n"
        "- categoria_dificultad: 'Básico', 'Intermedio' o 'Avanzado'."
    ),
    FormatoSalidaEnum.QUIZ_INTERACTIVO: (
        "FORMATO SOLICITADO: QUIZ INTERACTIVO DE EVALUACIÓN.\n"
        "Genera entre 3 y 5 preguntas de opción múltiple estructuradas.\n"
        "Para cada pregunta incluye:\n"
        "- pregunta: Planteamiento del escenario o pregunta conceptual.\n"
        "- opciones: Exactamente 4 opciones (lista de strings).\n"
        "- indice_correcto: Entero de 0 a 3 indicando la respuesta correcta.\n"
        "- justificacion_tecnica: Explicación exhaustiva del porqué es la opción válida.\n"
        "- explicacion_distractores: Análisis de por qué cada una de las otras 3 opciones es inválida.\n"
        "- pista_didactica: Pista orientadora sin revelar directamente la respuesta."
    ),
    FormatoSalidaEnum.MAPA_MENTAL: (
        "FORMATO SOLICITADO: MAPA MENTAL JERÁRQUICO DE TRES NIVELES.\n"
        "Organiza el contenido del documento alrededor de su tema central:\n"
        "- nodo_central: el tema central.\n"
        "- descripcion_general: síntesis breve del alcance del mapa.\n"
        "- ramas: entre 3 y 6 ideas principales del documento. Cada rama tiene entre 2 y 5 subtemas, "
        "y cada subtema entre 0 y 3 detalles breves (cifras, ejemplos o condiciones de la fuente).\n"
        "Las etiquetas son frases cortas (máximo 8 palabras), no oraciones completas. "
        "No escribas código Mermaid: el diagrama se genera a partir de las ramas."
    ),
    FormatoSalidaEnum.GUIA_PASO_A_PASO: (
        "FORMATO SOLICITADO: GUÍA PASO A PASO (TUTORIAL PRÁCTICO).\n"
        "Construye la guía solo con los procedimientos que describe la fuente:\n"
        "- prerrequisitos: lo que se necesita antes de empezar.\n"
        "- pasos: lista numerada (numero_paso desde 1) con titulo_paso, instrucciones detalladas, "
        "bloque_codigo cuando la fuente incluya comandos o código, y resultado_esperado como comprobación.\n"
        "- resumen_cierre: síntesis de lo logrado al completar la guía.\n"
        "No inventes pasos ni comandos que la fuente no describa."
    ),
    FormatoSalidaEnum.RESUMEN_EJECUTIVO: (
        "FORMATO SOLICITADO: RESUMEN EJECUTIVO (TL;DR ESTRATÉGICO).\n"
        "Incluye un resumen en un párrafo, puntos clave de alto impacto, análisis de impacto en el negocio "
        "y recomendaciones concretas de implementación."
    )
}


def obtener_instrucciones_formato(formato: str) -> str:
    """Retorna las directrices específicas de salida para el formato seleccionado."""
    try:
        enum_val = FormatoSalidaEnum(formato)
        return INSTRUCCIONES_FORMATOS[enum_val]
    except Exception:
        return INSTRUCCIONES_FORMATOS[FormatoSalidaEnum.FLASHCARDS]
