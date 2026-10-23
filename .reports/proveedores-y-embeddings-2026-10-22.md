# Reporte de validación — proveedores por etapa y embeddings locales

**Fecha:** 2026-10-22
**Spec:** `specs/nueva_mente/ia_proveedores_y_embeddings.md`
**Pruebas automáticas:** 73 pasan sin red (`uv run pytest`)

## CA1. Pruebas sin red ✅

Cubiertas en `tests/test_proveedores.py`:

- Gemini por defecto en todas las etapas.
- Groq sin clave usa Gemini.
- Respaldo de Groq a Gemini ante un error.
- Un prompt que no cabe en Groq va directo a Gemini.
- Una colección por modelo de embeddings.
- Embeddings locales sin control de cuota.

La prueba de colecciones detectó un error que se corrigió: al recortar el nombre a 63 caracteres, MiniLM y mpnet compartían la misma colección.

## CA2. Crítico en Groq ✅

**Cuenta gratuita de Groq** (cabeceras `x-ratelimit`):
- Modelos disponibles: `openai/gpt-oss-120b`, `openai/gpt-oss-20b` y `qwen/qwen3.8-27b`, con 8.000 tokens por minuto y 1.000 peticiones cada uno.
- `llama-3.3-70b-versatile` no está disponible.
- Modelo elegido: `openai/gpt-oss-120b`.

Casos de IA-07 con fragmentos de "JWT en OCI.pdf":

| Caso | Score | Criterio |
|---|---|---|
| Fiel | 1,0 / 1,0 / 1,0 | ≥ 0,85 ✅ |
| Datos inventados | 0,0 / 0,0 | < 0,75 ✅ |
| Fiel con analogías | 1,0 / 1,0 | ≥ 0,85 ✅ |

En una ejecución previa, con un subconjunto de fragmentos que no mencionaba "claves estáticas", el juez calificó correctamente la tarjeta como parcial (0,75).

**Pipeline completo con `IA_PROVIDER_CRITICO=groq`:**
- Documento pequeño (Fintech): el crítico usó Groq; score 1,0.
- "VCN y subredes": el prompt del crítico (~11.121 tokens) supera el máximo de Groq (5.600) y fue directo a Gemini; score 1,0.

**Limitación:** con la cuenta gratuita, Groq solo recibe críticas de documentos pequeños (fragmentos de hasta unos 4.500 tokens). Por eso `IA_PROVIDER_CRITICO` sigue en `gemini` por defecto.

## CA3. Embeddings locales frente a Gemini ✅

`scripts/comparar_embeddings.py`: 9 documentos (3 de TI y 6 reales), 27 consultas con los conceptos clave de cada documento, top-4 dentro del documento y juicio de relevancia por pooling con Gemini. Detalle en `.reports/embeddings-comparacion-2026-10-22.md`.

| Modelo | Hit@4 | Precision@4 | MRR | Indexación de los 9 documentos |
|---|---|---|---|---|
| Gemini `gemini-embedding-001` | 0,96 | 0,63 | 0,87 | 485 s (esperas de cuota) |
| Local MiniLM-L12 (0,22 GB) | 0,93 | 0,53 | 0,70 | 62 s |
| **Local mpnet-base (1 GB)** | **0,96** | 0,58 | 0,83 | 314 s (incluye la descarga del modelo) |

mpnet iguala a Gemini en Hit@4 (criterio: no bajar más de 0,10) y queda apenas por debajo en Precision@4 (−0,05) y MRR (−0,04). **Se adopta como valor por defecto.**

**Observación:** una pregunta en español sobre el tutorial de Python, que está en inglés, devolvió secciones poco precisas. La búsqueda entre idiomas es más débil con el modelo local. Las consultas del pipeline salen de los conceptos clave del propio documento, en su mismo idioma.

## CA4. Documento grande con embeddings locales ✅

"TutorialPython.pdf" (89 chunks, ~81k tokens): indexado en **67,5 s sin esperas por cuota**. Con Gemini, el mismo documento necesitó unos 4 minutos y 12 esperas.

## Documentos reales de Salud, Fintech y Marketing digital

Seis documentos reales (`tests/fixtures/documentos_reales.md`), pipeline completo con Gemini real:

| Documento | Dominio detectado | Perfil | Formato | Score | 429 |
|---|---|---|---|---|---|
| Definiciones de salud.pdf | Salud | Junior | Flashcards | 1,0 | 0 |
| Tema-11_SALUD-PUBLICA.pdf | Salud | Senior | Quiz Interactivo | 1,0 | 0 |
| LatamFintechMarket2025.pdf | Fintech | Ejecutivo | Resumen Ejecutivo | 1,0 | 0 |
| Mariana_GutierrezSanchez_…_2023.pdf | Fintech | Junior | Mapa Mental | 1,0 | 0 |
| Marketing_Digital_para_emprendedores.pdf | Marketing digital | Junior | Flashcards | 1,0 | 0 |
| elementos-marketing-digital.pdf (157 págs.) | Marketing digital | Senior | Quiz Interactivo | 1,0 | 0 |

Repetición con la configuración final (embeddings locales): "Tema-11_SALUD-PUBLICA.pdf", Junior, Mapa Mental, Salud → score 1,0 en 23,3 s.

## Correcciones asociadas

- `scripts/validate_retrieval.py` usaba `gemini-2.5-flash`, que ya no está disponible para claves nuevas, y pasaba en silencio a una heurística de palabras. Ahora usa el modelo configurado y avisa si recurre a la heurística.
