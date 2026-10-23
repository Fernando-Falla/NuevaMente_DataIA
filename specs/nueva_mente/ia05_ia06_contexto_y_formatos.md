# Spec IA-05 / IA-06: selección de contexto y calidad de los formatos

## Contexto

Línea base medida (ADR-001; tokens reales de Gemini, generación + crítico, perfil Junior):

- Una generación consume unos 11k tokens con "JWT en OCI" (9 chunks) y unos 27k con "Tema-11 Salud Pública" (21 chunks). Entre el 90 % y el 98 % es **entrada**: los fragmentos del documento, enviados al generador y al crítico.
- El contexto se arma con `similarity_search(k=15)` contra una consulta genérica armada con el título y el formato. En documentos grandes (73 chunks) cubre una fracción y no sigue la estructura; en pequeños envía casi todo.
- La metadata pedagógica del documento (conceptos clave, prerrequisitos, resumen) no llega a la generación. Los `conceptos_clave` de la respuesta salen de una heurística de palabras con mayúscula ("Notas, Gateway, Oracle…").
- **Mapa Mental:** el árbol sale con un solo nivel (4 nodos en Salud Pública) y el detalle queda solo en el Mermaid que escribe el modelo (44 líneas). Árbol y Mermaid no coinciden.
- **Guía Paso a Paso:** se genera aunque el documento no tenga procedimientos.
- El generador recibe un esquema con una unión de los cinco formatos (`items: Union[...]`), de modo que el modelo elige la forma.

## Requisitos

### IA-05: selección de contexto

- **R1.** El contexto se arma con **todos** los chunks del documento (`get_document_chunks`) y se selecciona dentro de un presupuesto `IA_CONTEXT_MAX_TOKENS` (8.000 por defecto). Si el documento cabe, se envía completo.
- **R2. Cobertura:** primero un chunk por sección, el de mayor prioridad para el formato; después se completa el presupuesto por prioridad. Los chunks elegidos se envían en el orden del documento.
- **R3. Prioridad por formato** según `tipo_contenido`:
  - Flashcards: `definicion`, luego `ejemplo` y `afirmacion`.
  - Quiz Interactivo: `afirmacion`, `procedimiento`, `definicion`.
  - Resumen Ejecutivo y Mapa Mental: cobertura por sección, sin preferencia de tipo.
  - Guía Paso a Paso: `procedimiento` y `codigo`.

  A igual prioridad, decide la similitud con los conceptos clave del documento (embeddings locales, sin cuota).
- **R4.** El crítico evalúa contra el mismo contexto seleccionado.

### IA-06: generación

- **R5.** La metadata pedagógica llega al grafo. Los `conceptos_clave` de la respuesta son los del documento; la heurística queda solo como respaldo. El generador recibe el resumen y los conceptos como orientación.
- **R6. Un esquema de salida por formato:** el generador recibe solo el del formato pedido. La respuesta conserva la forma de `PaqueteContenidoAdaptado`.
- **R7. Mapa Mental:** el modelo completa un esquema **sin recursión**: ramas (3 a 6), cada una con subtemas (2 a 5) y detalles opcionales. El código arma `arbol` (con ids) y `codigo_mermaid` desde ese esquema; el modelo no escribe Mermaid.
- **R8. Guía Paso a Paso:** antes de generar, si menos de 2 chunks, o menos del 15 % de los chunks del documento, son `procedimiento` o `codigo`, se rechaza con `FORMATO_NO_ADECUADO`, sugiriendo otro formato. Medido: Salud Pública (1 chunk, 5 %), Mariana Gutiérrez (1, 3 %) y LatamFintech (1, 17 %) se rechazan; JWT (4, 44 %), VCN (5, 36 %), TutorialPython (30, 34 %) y elementos-marketing (28, 38 %) se generan.

## Criterios de aceptación

- **CA1. Pruebas sin red:** selección (documento completo si cabe, cobertura por sección, prioridad por formato, orden del documento, presupuesto), conversión del mapa a árbol y Mermaid, y rechazo de la guía.
- **CA2. Tokens:** con "Tema-11 Salud Pública", la entrada total baja al menos un 30 % frente a la línea base (27k), sin bajar el score del crítico (≥ 0,85).
- **CA3. Mapa Mental:** con Salud Pública y JWT, el árbol tiene al menos 2 niveles y 10 nodos, y el Mermaid coincide con el árbol.
- **CA4. Guía Paso a Paso:** se rechaza en un documento conceptual (Salud Pública) y se genera en uno con procedimientos.
- **CA5.** Los conceptos clave de la respuesta coinciden con los de la metadata del documento.
- **CA6.** Los 5 formatos × 3 perfiles se generan con score ≥ 0,85 en al menos un documento real.
