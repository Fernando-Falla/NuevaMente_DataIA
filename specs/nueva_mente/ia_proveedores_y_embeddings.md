# Spec: proveedor de LLM por etapa y embeddings locales

## Contexto

Consumo medido con "TutorialPython.pdf" (81k tokens) en la cuenta gratuita de Gemini:

| Etapa | Llamadas | Tokens aprox. | Límite que la condiciona |
|---|---|---|---|
| Metadata del documento | 1 | 8k | — |
| Clasificación de chunks | 7 | 81k | Peticiones por día |
| Embeddings | 15 lotes | 81k | **Tokens por minuto: produjo los 429** |
| Generador y crítico | 2–4 | 12–15k cada una | — |

Hallazgos:

- La cuota de Gemini es por proyecto, no por clave. Usar varias cuentas gratuitas para sumar cuota contradice los términos del proveedor, así que no se adopta.
- El "failover automático a Groq" de `config.py` no funciona: `langchain-groq` no está instalado y el `ImportError` se ignora.
- Un crítico de la misma familia de modelos que el generador tiende a ser indulgente con su propio texto.

## Requisitos

- **R1. Proveedor por etapa.** `IA_PROVIDER_CLASIFICACION` (metadata del documento y clasificación de chunks), `IA_PROVIDER_GENERACION` e `IA_PROVIDER_CRITICO` aceptan `gemini` o `groq`. Por defecto, `gemini` en todas.
- **R2. Respaldo.** Si la etapa usa Groq y falla con un error del proveedor, se reintenta con Gemini. Si no hay `GROQ_API_KEY`, la etapa usa Gemini y se registra una advertencia.
- **R3. Cuota de Groq.** Tiene su propio control de ritmo: `IA_GROQ_RPM` (30) e `IA_GROQ_TPM` (8.000), según las cabeceras `x-ratelimit` de la cuenta gratuita. Modelo: `GROQ_MODEL` (`openai/gpt-oss-120b`; `llama-3.3-70b-versatile` no está disponible en la cuenta). Un prompt mayor que `IA_GROQ_MAX_PROMPT_TOKENS` (70 % de la cuota por minuto) va directo a Gemini, porque Groq lo rechazaría.
- **R4. Embeddings configurables.** `DATAIA_EMBEDDINGS` acepta:
  - `local` (por defecto desde la validación de CA3): `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` con `fastembed`, en CPU y sin cuota (`DATAIA_LOCAL_EMBEDDING_MODEL`).
  - `gemini`: `models/gemini-embedding-001`.
- **R5. Colecciones separadas por modelo de embeddings,** porque las dimensiones difieren y los vectores no son comparables. El nombre de la colección incluye el modelo cuando no es el de Gemini.
- **R6. Dependencias:** `langchain-groq` y `fastembed`. El respaldo de `config.py` deja de fallar en silencio.

## Criterios de aceptación

- **CA1.** Pruebas sin red: selección de proveedor por etapa, respaldo a Gemini sin clave de Groq, colección por modelo de embeddings y embeddings locales sin control de cuota.
- **CA2.** Con la clave real de Groq, el crítico en Groq repite los casos CA1–CA3 de IA-07 (fiel ≥ 0,85, inventado < 0,75, analogías ≥ 0,85).
- **CA3.** Embeddings locales frente a Gemini con `scripts/comparar_embeddings.py` (búsqueda dentro del documento, juicio de relevancia por pooling): se adoptan por defecto solo si el Hit@4 promedio (el proxy de Recall de `validate_retrieval.py`) no baja más de 0,10.
- **CA4.** Un documento de unos 80k tokens se indexa con embeddings locales sin esperas por cuota.
