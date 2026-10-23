"""
IA-05: selección del contexto que reciben el generador y el crítico.

En lugar de una búsqueda por similitud con k fijo, se parte de todos los chunks
del documento y se eligen por cobertura de secciones y por el tipo de contenido
que mejor sirve al formato, dentro de un presupuesto de tokens
(spec specs/nueva_mente/ia05_ia06_contexto_y_formatos.md, R1-R3 y R8).
"""

import os
from typing import Dict, List, Optional

from langchain_core.documents import Document

from dataia.common.budget import estimate_tokens

# Tipos de contenido preferidos por formato; los no listados quedan después.
# Resumen y Mapa Mental no priorizan tipos: buscan cobertura de secciones.
PRIORIDAD_POR_FORMATO: Dict[str, List[str]] = {
    "Flashcards": ["definicion", "ejemplo", "afirmacion"],
    "Quiz Interactivo": ["afirmacion", "procedimiento", "definicion"],
    "Resumen Ejecutivo": [],
    "Mapa Mental": [],
    "Guia Paso a Paso": ["procedimiento", "codigo"],
}

TIPOS_PROCEDIMENTALES = ("procedimiento", "codigo")
MIN_CHUNKS_GUIA = 2
MIN_PROPORCION_GUIA = 0.15


def presupuesto_contexto() -> int:
    return int(os.getenv("IA_CONTEXT_MAX_TOKENS", "8000"))


def _orden(doc: Document) -> str:
    # chunk_id termina en un índice con ceros a la izquierda: ordena como el documento
    return doc.metadata.get("chunk_id", "")


def _prioridad(doc: Document, formato: str) -> int:
    preferidos = PRIORIDAD_POR_FORMATO.get(formato, [])
    tipo = doc.metadata.get("tipo_contenido")
    return preferidos.index(tipo) if tipo in preferidos else len(preferidos)


def seleccionar_contexto(
    chunks: List[Document],
    formato: str,
    similitud: Optional[Dict[str, float]] = None,
    max_tokens: Optional[int] = None,
) -> List[Document]:
    """
    Devuelve los chunks elegidos, en el orden del documento:
    1. Si el documento cabe en el presupuesto, todos.
    2. Si no, el mejor chunk de cada sección (cobertura) y luego los de mayor
       prioridad, sin superar el presupuesto. Siempre al menos uno.
    A igual prioridad decide la similitud con los conceptos clave del documento.
    """
    if not chunks:
        return []
    max_tokens = max_tokens or presupuesto_contexto()
    similitud = similitud or {}
    tokens = {id(c): estimate_tokens(c.page_content) for c in chunks}
    if sum(tokens.values()) <= max_tokens:
        return sorted(chunks, key=_orden)

    def clave(doc: Document):
        return (_prioridad(doc, formato), -similitud.get(doc.metadata.get("chunk_id", ""), 0.0), _orden(doc))

    mejor_por_seccion: Dict[str, Document] = {}
    for doc in sorted(chunks, key=clave):
        mejor_por_seccion.setdefault(doc.metadata.get("section") or "", doc)

    elegidos: List[Document] = []
    vistos = set()
    usados = 0
    for doc in sorted(mejor_por_seccion.values(), key=clave) + sorted(chunks, key=clave):
        if id(doc) in vistos:
            continue
        vistos.add(id(doc))
        if usados + tokens[id(doc)] <= max_tokens or not elegidos:
            elegidos.append(doc)
            usados += tokens[id(doc)]
    return sorted(elegidos, key=_orden)


def verificar_pertinencia_formato(formato: str, chunks: List[Document]) -> Optional[str]:
    """
    Mensaje de rechazo si el formato no es adecuado para el documento (spec IA-06 R8),
    o None si lo es. Hoy solo aplica a la Guía Paso a Paso.
    """
    if formato != "Guia Paso a Paso" or not chunks:
        return None
    procedimentales = sum(1 for c in chunks if c.metadata.get("tipo_contenido") in TIPOS_PROCEDIMENTALES)
    proporcion = procedimentales / len(chunks)
    if procedimentales < MIN_CHUNKS_GUIA or proporcion < MIN_PROPORCION_GUIA:
        return (
            f"El documento tiene {procedimentales} de {len(chunks)} fragmentos con procedimientos o código "
            f"({proporcion:.0%}); una Guía Paso a Paso requiere al menos {MIN_CHUNKS_GUIA} y el "
            f"{MIN_PROPORCION_GUIA:.0%}. Use Flashcards, Quiz Interactivo, Resumen Ejecutivo o Mapa Mental."
        )
    return None
