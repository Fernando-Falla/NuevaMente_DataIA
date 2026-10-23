# ADR-002: Embeddings locales por defecto y proveedor de LLM por etapa

**Fecha:** 2026-10-22
**Estado:** Aceptada
**Enmienda:** Constitución, §2 "Stack Técnico Oficial" (Embeddings, Extracción PDF, Lenguaje)

## Contexto

- La constitución fijaba Gemini `text-embedding-004` para los embeddings, con un respaldo local permitido. Ese modelo responde 404; se usa `models/gemini-embedding-001`.
- Con la cuenta gratuita, los embeddings de Gemini fueron el origen de los errores 429 (30.000 tokens por minuto). Un documento de 81k tokens tardaba unos 4 minutos, con 12 esperas por cuota.
- La comparación con 9 documentos y 27 consultas (`.reports/embeddings-comparacion-2026-10-22.md`) dio a `paraphrase-multilingual-mpnet-base-v2` (fastembed, CPU) el mismo Hit@4 que Gemini (0,96), con Precision@4 0,58 frente a 0,63 y MRR 0,83 frente a 0,87. Con el modelo local, el mismo documento se indexa en 67 s sin esperas.
- La extracción pasó de `fitz` a `pymupdf` + `pymupdf4llm` (Markdown con títulos), y el entorno usa Python 3.14.

## Decisión

1. **Embeddings locales por defecto** (`DATAIA_EMBEDDINGS=local`). Gemini `gemini-embedding-001` queda disponible con `DATAIA_EMBEDDINGS=gemini`. Una colección de ChromaDB por modelo.
2. **Proveedor de LLM configurable por etapa** (clasificación, generación, crítico): Gemini por defecto, Groq opcional con respaldo en Gemini. El crítico en Groq se validó (spec `ia_proveedores_y_embeddings.md`). Con la cuenta gratuita de Groq (8.000 tokens por minuto) solo recibe prompts pequeños, por lo que Gemini sigue siendo el valor por defecto.
3. **No se usan varias cuentas gratuitas para sumar cuota:** la cuota de Gemini es por proyecto y los términos del proveedor prohíben eludir sus límites.

## Consecuencias

- La primera ejecución descarga el modelo de embeddings (~1 GB) en `.dataia_models/`.
- La búsqueda entre idiomas (consulta en español sobre un documento en inglés) es más débil con el modelo local.
- Los vectores indexados con Gemini no se reutilizan con el modelo local: el documento se reindexa sin costo de cuota.
