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

    for rama in arbol:
        etiqueta_rama = limpiar_texto_nodo_mermaid(rama.get("etiqueta", "Rama Principal"))
        lineas.append(f"    {etiqueta_rama}")
        subnodos = rama.get("subnodos", [])
        if isinstance(subnodos, list):
            for sub in subnodos:
                if isinstance(sub, dict):
                    txt_sub = limpiar_texto_nodo_mermaid(sub.get("etiqueta", "Detalle"))
                else:
                    txt_sub = limpiar_texto_nodo_mermaid(str(sub))
                lineas.append(f"      {txt_sub}")

    return "\n".join(lineas)


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
        return f"mindmap\n  root(({raiz}))\n    Fundamentos\n      Conceptos Clave\n    Arquitectura\n      Componentes\n    Buenas Prácticas\n      Seguridad"

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
