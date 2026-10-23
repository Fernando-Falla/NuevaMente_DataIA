# Reporte de validación — IA-05 (selección de contexto) e IA-06 (formatos)

**Fecha:** 2026-10-22
**Spec:** `specs/nueva_mente/ia05_ia06_contexto_y_formatos.md`
**Configuración:** Gemini `gemini-3.5-flash-lite` (generación y crítico), embeddings locales mpnet, `IA_CONTEXT_MAX_TOKENS=8000`, `IA_STRICT_PROVIDERS=1`
**Pruebas automáticas:** 85 pasan sin red

## CA1. Pruebas sin red ✅

En `tests/test_contexto_y_formatos.py` se cubre:

- documento completo cuando cabe en el presupuesto;
- presupuesto respetado, un chunk por sección, prioridad por formato y orden del documento;
- desempate por similitud y al menos un chunk siempre;
- pertinencia de la guía (cuatro casos);
- conversión del mapa a árbol y Mermaid coincidentes;
- un esquema por formato en el generador;
- conceptos del documento en el analizador.

## CA2. Tokens ✅

Tokens reales informados por Gemini (generación + crítico, perfil Junior), antes y después:

| Documento | Formato | Entrada antes | Entrada después | Cambio |
|---|---|---|---|---|
| Tema-11 Salud Pública (21 chunks) | Flashcards | 27.766 | 16.877 | −39 % |
| | Quiz Interactivo | 28.053 | 16.611 | −41 % |
| | Resumen Ejecutivo | 27.145 | 15.738 | −42 % |
| | Mapa Mental | 27.036 | 17.158 | −37 % |
| JWT en OCI (9 chunks) | 4 formatos | 10.805–13.014 | 11.266–12.118 | ≈ 0 % (el documento cabe completo en el presupuesto) |

Todas las generaciones de Salud Pública superaron el umbral del crítico.

## CA3. Mapa Mental ✅

| Documento | Antes | Después |
|---|---|---|
| Tema-11 Salud Pública | 4 nodos, 1 nivel; Mermaid de 44 líneas que no coincidía | 40 nodos (5 / 11 / 24 por nivel); Mermaid de 40 líneas, una por nodo |
| JWT en OCI | 1 nivel | 27 nodos (4 / 8 / 15) |
| elementos-marketing-digital (Ejecutivo) | — | 33 nodos (4 / 9 / 20), ramas orientadas al negocio |

La salida del mapa pasó de ~500 a ~800–1.000 tokens, por ser más completo; sigue entre las más bajas de los cinco formatos.

## CA4. Guía Paso a Paso ✅

- Tema-11 Salud Pública: rechazada con `Formato No Adecuado` en 1,5 s, sin llamadas al LLM ("1 de 21 fragmentos con procedimientos o código (5 %)").
- JWT en OCI y elementos-marketing-digital: generadas (en el perfil Ejecutivo, 6 pasos y 3 prerrequisitos).

## CA5. Conceptos clave ✅

La respuesta trae los conceptos de la metadata del documento: "Salud Pública, Binomio Salud-Enfermedad, Determinantes de la salud" en lugar de la heurística anterior ("Notas, Gateway, Oracle…").

## CA6. 5 formatos × 3 perfiles ✅

"elementos-marketing-digital.pdf" (real, 157 páginas, 73 chunks), nicho Marketing digital:

| Perfil | Flashcards | Quiz Interactivo | Resumen Ejecutivo | Mapa Mental | Guía Paso a Paso |
|---|---|---|---|---|---|
| Junior | 1,0 (6) | 1,0 (4) | 1,0 | 1,0 | 1,0 |
| Senior | 1,0 (6) | 1,0 (3) | 1,0 | 1,0 | 1,0 |
| Ejecutivo | 1,0 (6) | 1,0 (3) | 1,0 | 1,0 | 1,0 |

Score del crítico (entre paréntesis, la cantidad de ítems). Entre 10 y 14 s por combinación; la primera, 64 s, incluyó la indexación del documento.

## Observaciones

- Las 15 combinaciones obtuvieron 1,0. El juez sí discrimina el contenido inventado (CA2 de IA-07), pero conviene repetir esas pruebas adversariales periódicamente para detectar si se vuelve indulgente.
- La similitud con los conceptos clave usa la distancia de Chroma: la "relevancia" que calcula Chroma supone vectores normalizados y con el modelo local daba valores fuera de [0, 1].
