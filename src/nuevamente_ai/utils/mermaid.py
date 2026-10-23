"""
Módulo utilitario determinista para validación, limpieza y generación
de sintaxis Mermaid.js para Mapas Mentales.
Opera de forma 100% local en Python (0 tokens de API, latencia < 1ms).
"""

import re
from typing import Any, Dict, List, Optional


def limpiar_texto_nodo_mermaid(texto: str) -> str:
    """
    Sanea el texto de un nodo para evitar colisiones sintácticas en Mermaid.js:
    - Reemplaza comillas dobles y saltos de línea.
    - Remueve paréntesis o corchetes conflictivos que rompen el parser de mindmap.
    """
    if not texto:
        return "Concepto"
    # Eliminar saltos de línea
    s = texto.replace("\n", " ").replace("\r", " ").strip()
    # Reemplazar comillas dobles
    s = s.replace('"', "'")
    # Limpiar caracteres que abren o cierran formas en Mermaid sin escapar
    s = re.sub(r"[(){}\[\]]", " ", s)
    # Normalizar espacios
    s = re.sub(r"\s+", " ", s).strip()
    return s[:60] if len(s) > 60 else s


def generar_mermaid_desde_arbol(nodo_central: str, arbol: List[Dict[str, Any]]) -> str:
    """
    Genera de forma determinista un diagrama 'mindmap' a partir de una lista
    de diccionarios o modelos de nodos arbóreos.
    """
    raiz = limpiar_texto_nodo_mermaid(nodo_central) or "Mapa Mental"
    lineas = ["mindmap", f"  root(({raiz}))"]

    def agregar(nodos: List[Any], sangria: int) -> None:
        # Recursivo: el árbol puede tener ramas, subtemas y detalles (spec IA-06 R7)
        for nodo in nodos if isinstance(nodos, list) else []:
            if isinstance(nodo, dict):
                etiqueta = limpiar_texto_nodo_mermaid(nodo.get("etiqueta", "Concepto"))
                hijos = nodo.get("subnodos", [])
            else:
                etiqueta, hijos = limpiar_texto_nodo_mermaid(str(nodo)), []
            lineas.append(" " * sangria + etiqueta)
            agregar(hijos, sangria + 2)

    agregar(arbol, 4)
    return "\n".join(lineas)


def mapa_generado_a_arbol(ramas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convierte el mapa sin recursión que genera el modelo (ramas → subtemas →
    detalles) en el árbol del contrato (NodoMapaMental con ids "1", "1.2", "1.2.1").
    """
    arbol = []
    for i, rama in enumerate(ramas, start=1):
        subnodos = []
        for j, subtema in enumerate(rama.get("subtemas", []), start=1):
            detalles = [
                {"id": f"{i}.{j}.{k}", "etiqueta": detalle, "subnodos": []}
                for k, detalle in enumerate(subtema.get("detalles", []), start=1)
            ]
            subnodos.append({"id": f"{i}.{j}", "etiqueta": subtema.get("etiqueta", ""), "subnodos": detalles})
        arbol.append({"id": str(i), "etiqueta": rama.get("etiqueta", ""), "subnodos": subnodos})
    return arbol


def sanitizar_codigo_mermaid(
    codigo: Optional[str],
    nodo_central: str = "Concepto Principal",
    arbol: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Valida y sanea un bloque de código Mermaid devuelto por el LLM.
    Si el código viene vacío, malformado o sin cabecera 'mindmap',
    lo reconstruye deterministamente a partir del árbol o parámetros base.
    """
    if not codigo or not isinstance(codigo, str) or not codigo.strip():
        if arbol:
            return generar_mermaid_desde_arbol(nodo_central, arbol)
        raiz = limpiar_texto_nodo_mermaid(nodo_central)
        # Estructura neutral respecto del dominio (spec IA-02c R5)
        return f"mindmap\n  root(({raiz}))\n    Conceptos principales\n    Procedimientos y reglas\n    Aplicación práctica"

    # 1. Remover etiquetas de Markdown ```mermaid ... ```
    texto = re.sub(r"^```(?:mermaid)?\s*", "", codigo.strip(), flags=re.IGNORECASE)
    texto = re.sub(r"\s*```$", "", texto.strip()).strip()

    # 2. Verificar cabecera
    lineas = texto.splitlines()
    if not lineas:
        return sanitizar_codigo_mermaid(None, nodo_central, arbol)

    primera_linea = lineas[0].strip().lower()
    if not primera_linea.startswith("mindmap"):
        lineas.insert(0, "mindmap")

    lineas_sanitizadas = [lineas[0].strip()]
    tiene_root = False

    for linea in lineas[1:]:
        linea_raw = linea.rstrip()
        if not linea_raw.strip():
            continue

        # Detectar indentación
        indent_len = len(linea_raw) - len(linea_raw.lstrip())
        contenido = linea_raw.strip()

        # Asegurar raíz
        if "root(" in contenido:
            tiene_root = True
            # Extraer contenido de root
            match_root = re.search(r"root\s*\(\((.*?)\)\)", contenido)
            if match_root:
                lbl = limpiar_texto_nodo_mermaid(match_root.group(1))
            else:
                lbl = limpiar_texto_nodo_mermaid(nodo_central)
            lineas_sanitizadas.append(f"  root(({lbl}))")
            continue

        # Sanitizar nodo hijo
        contenido_limpio = limpiar_texto_nodo_mermaid(contenido)
        indent = " " * max(4, indent_len)
        lineas_sanitizadas.append(f"{indent}{contenido_limpio}")

    # Si no tenía root formal, insertarlo después de 'mindmap'
    if not tiene_root and len(lineas_sanitizadas) > 1:
        raiz = limpiar_texto_nodo_mermaid(nodo_central)
        lineas_sanitizadas.insert(1, f"  root(({raiz}))")

    return "\n".join(lineas_sanitizadas)
