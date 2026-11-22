# NuevaMente — Data & IA Pipeline

Pipeline de **ingestión → chunking → embeddings → vector store → generación → validación de fidelidad** que convierte documentación técnica (PDF, Markdown, TXT) en material educativo adaptado al perfil del lector: flashcards, quiz, resumen ejecutivo, mapa mental o guía paso a paso.

> **El caso en 30 segundos**
> - **Problema:** convertir documentación técnica en material de estudio adaptado al lector, sin perder la trazabilidad ni inventar contenido.
> - **Decisión:** chunking estructural que protege código y tablas, metadata pedagógica por documento y por fragmento, embeddings elegidos con métricas y un juez de fidelidad por ítem.
> - **Resultado medido:** en una comparación de 9 documentos y 27 consultas, los embeddings locales lograron el mismo Hit@4 que Gemini (0,96) y sin esperas de cuota. El juez original daba 0,5 o 1,0 al contenido fiel con analogías según la corrida; el juez por ítem da 1,0 en ambas y mantiene 0,0 con datos inventados. 73 pruebas automáticas sin red.
>
> **In English:** Pipeline that turns technical documents (PDF, Markdown, TXT) into learning material adapted to the reader: flashcards, quizzes, summaries, mind maps and step-by-step guides. Structure-aware chunking keeps code and tables intact. Local embeddings were chosen after a 27-query comparison (same Hit@4 as Gemini, 0.96, with no quota waits). A per-item faithfulness judge (LLM-as-a-judge) flags made-up content. FastAPI backend with SSE streaming and 73 offline tests. Built for the ONE G10 hackathon, extending the team's AI Core.

> **Contexto:** nació en el **Hackathon ONE G10** (Alura Latam / Oracle Next Education, equipo G10-LATAM-EQUIPO15, sep – nov 2026). Para aprender y practicar, decidí desarrollarlo completo en este repositorio personal: cloné la estructura inicial del AI Core del equipo y, sobre ella, extendí el pipeline hasta la generación, la validación de fidelidad y la API.

## Mi rol

- **En el hackathon (squad Data & IA):** responsable de la ingestión (IA-02), el chunking (IA-03) y la vectorización (IA-04), incluida la validación del retrieval.
- **En este repositorio (oct – nov 2026):** partí de la estructura inicial del AI Core del equipo (un grafo de agentes con LangGraph) y la extendí: selección de contexto por cobertura (IA-05), generación en 5 formatos × 3 perfiles usando la metadata pedagógica (IA-06), juez de fidelidad por ítem (IA-07), contrato JSON con el backend (IA-08), backend FastAPI unificado (BE-01) y streaming SSE de progreso (BE-02).
- **Cómo se desarrolló:** con Spec Driven Development y agentes de IA. Yo definí las especificaciones y los ADRs (`specs/`), oriento las decisiones y valido los resultados con los reportes de `.reports/`; los agentes generan el código y ejecutan las pruebas.

## Qué demuestra este proyecto

- **Chunking estructural:** el splitter protege bloques de código y tablas Markdown antes de cortar, y conserva `page`, `page_end` y `section` para la trazabilidad (`document_id` → `chunk_id` → fuente).
- **Decisiones medidas:** los embeddings locales (`paraphrase-multilingual-mpnet-base-v2`) se adoptaron por defecto tras compararlos con Gemini en 9 documentos y 27 consultas: igual Hit@4 (0,96), −0,05 en Precision@4 y sin esperas de cuota (ver [Evaluación](#evaluación)).
- **LLM-as-a-judge para fidelidad:** el juez por ítem distingue contenido fiel (1,0) de contenido con datos inventados (0,0), y corrigió un falso negativo del juez original en contenido fiel con analogías (0,5 → 1,0).
- **Operación con cuotas gratuitas:** límites de tamaño antes de llamar al LLM, control de RPM/TPM, reintentos ante `429` y proveedor por etapa (Gemini o Groq) con fallback.
- **Contratos explícitos:** DTOs con Pydantic v2, errores tipados (no excepciones crudas), ADRs y pruebas con pytest sin red ni LLM.

---

## Arquitectura

```text
Documento (PDF / MD / TXT)
        │
        ▼
┌──────────────────────┐
│ IA-02 Ingestión      │  validación · límites · extracción (PyMuPDF/pymupdf4llm) · normalización
│                      │  + metadata pedagógica y dominio (Gemini, con caché local)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ IA-03 Chunking       │  splitter estructural (protege código y tablas) · 800/150
│                      │  + clasificación de chunks en lotes (Gemini o Groq)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ IA-04 Vector store   │  embeddings locales (fastembed, mpnet) o Gemini · ChromaDB persistente
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ IA-05 a IA-07        │  selección de contexto por cobertura → generación por perfil y formato
│ (AI Core, LangGraph) │  → juez de fidelidad por ítem → auditoría de integridad
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ IA-08 / BE-01 / BE-02│  contrato JSON · FastAPI · streaming SSE · persistencia opcional en OCI Object Storage
└──────────────────────┘
```

## Evaluación

Reportes completos en `.reports/`.

**Retrieval (IA-04, 29-sep-2026):** 5 consultas sobre documentos de TI, `top_k=4`. Recall@4 = 1,00 en las 5. Precision@4 = 1,00 en 4 y 0,25 en una. Es un set pequeño: sirvió para validar la etapa, no como benchmark. La relevancia de cada fragmento la juzgó un LLM (Gemini). Recall@4 aquí es un proxy: vale 1 si hay al menos un fragmento relevante entre los 4 primeros (equivale a Hit@4).

**Embeddings (22-oct-2026):** 9 documentos (TI, Salud, Fintech y Marketing digital), 27 consultas, `top_k=4`, relevancia juzgada por pooling con Gemini.

| Modelo | Hit@4 | Precision@4 | MRR | Indexación |
|---|---|---|---|---|
| `gemini-embedding-001` | 0,96 | 0,63 | 0,87 | 485 s (esperas de cuota) |
| `paraphrase-multilingual-MiniLM-L12-v2` (local) | 0,93 | 0,53 | 0,70 | 62 s |
| **`paraphrase-multilingual-mpnet-base-v2` (local, por defecto)** | **0,96** | 0,58 | 0,83 | 314 s (incluye la descarga) |

Limitación observada: la búsqueda entre idiomas (pregunta en español sobre un documento en inglés) es más débil con el modelo local.

**Fidelidad (IA-07, 22-oct-2026):** juez por ítem, dos ejecuciones por caso.

| Caso | Juez original del equipo | Juez por ítem | Criterio |
|---|---|---|---|
| Fiel al documento | 1,0 / 1,0 | 1,0 / 1,0 | ≥ 0,85 |
| Con datos inventados | 0,0 / 0,0 | 0,0 / 0,0 | < 0,75 |
| Fiel, con analogías | 0,5 / 1,0 | 1,0 / 1,0 | ≥ 0,85 |

**Pruebas automáticas:** 73 pasan sin red (`uv run pytest`, 22-oct-2026).

---

## Dominios soportados

NuevaMente procesa documentos técnicos de **TI, Fintech, Salud y Marketing digital**. El dominio se detecta en la ingestión: lo clasifica Gemini y, si no está disponible, un léxico por dominio. Los documentos de otros dominios o no técnicos se rechazan con `DOMINIO_NO_SOPORTADO`. La generación agrega pautas de exactitud propias de cada dominio; por ejemplo, en Salud reproduce dosis y umbrales exactos y aclara que es material educativo.

El **nicho** (`TI`, `Fintech`, `Salud`, `Marketing digital`, `General`) es otro concepto: el sector al que se adaptan los ejemplos, elegido por quien solicita el contenido.

## Límites de tamaño y cuota

| Límite | Valor por defecto | Error |
|---|---|---|
| Tamaño del archivo | 25 MB | `ARCHIVO_DEMASIADO_GRANDE` |
| Páginas de un PDF | 300 | `DOCUMENTO_DEMASIADO_EXTENSO` |
| Tokens estimados del documento | 150.000 | `DOCUMENTO_DEMASIADO_EXTENSO` |

Los rechazos ocurren antes de llamar al LLM. Las llamadas a Gemini respetan límites por minuto configurables, pensados para la cuenta gratuita, y ante un `429` esperan y reintentan. Detalle: `specs/nueva_mente/ia02_tamano_y_cuota.md` y `.reports/ia02-tamano-y-dominios-2026-10-22.md`.

## Proveedores por etapa

Cada etapa puede usar Gemini o Groq: `IA_PROVIDER_CLASIFICACION` (metadata y clasificación de chunks), `IA_PROVIDER_GENERACION` e `IA_PROVIDER_CRITICO`. Usar otro proveedor en el crítico da una evaluación más independiente del generador y reparte la cuota. Si Groq falla, no hay `GROQ_API_KEY` o el prompt no cabe en su cuota por minuto (8.000 tokens en la cuenta gratuita), la etapa usa Gemini.

Con la cuenta gratuita de Groq, el crítico solo cabe en documentos pequeños (fragmentos de hasta ~4.500 tokens); por eso `IA_PROVIDER_CRITICO` queda en `gemini` por defecto. Detalle: `specs/nueva_mente/ia_proveedores_y_embeddings.md`.

No se recomienda usar varias cuentas gratuitas para sumar cuota: la cuota de Gemini es por proyecto, no por clave, y los términos del proveedor prohíben eludir sus límites.

## Stack

| Componente | Tecnología |
|-|-|
| Lenguaje | Python ≥ 3.14 |
| Gestor de entorno | [uv](https://github.com/astral-sh/uv) |
| Extracción PDF | PyMuPDF + `pymupdf4llm` (Markdown con títulos y secciones; respaldo a texto plano por página) |
| Validación / DTOs | Pydantic v2 |
| LLM | Gemini (por defecto `gemini-3.5-flash-lite`, configurable con `GEMINI_MODEL`) y Groq (`openai/gpt-oss-120b`) por etapa |
| Chunking | LangChain Text Splitters (Recursive, 800/150) + splitter estructural propio sobre el documento completo |
| Embeddings | Locales con fastembed (`paraphrase-multilingual-mpnet-base-v2`) por defecto; `gemini-embedding-001` opcional |
| Vector store | ChromaDB (persistente, colección `nuevamente_docs`, ids estables por `chunk_id`) + registro por documento |
| Generación | AI Core del equipo: agentes orquestados con LangGraph |
| API | FastAPI + SSE |
| Almacenamiento (opcional) | OCI Object Storage |
| Pruebas | pytest |

---

## Estructura del repositorio

```text
.
├── src/
│   ├── dataia/                   # IA-02 a IA-04
│   │   ├── ingestion/            # Extracción, validación y metadata pedagógica
│   │   ├── chunking/             # Splitter estructural y clasificación de chunks
│   │   ├── vectorstore/          # Cliente ChromaDB y registro por documento
│   │   └── common/               # Modelos Pydantic, credenciales y límites del proveedor
│   ├── nuevamente_ai/            # IA-05 a IA-08 (AI Core del equipo, adaptado)
│   │   └── agents/critico.py     # IA-07: juez de fidelidad por ítem
│   └── backend/                  # BE-01 y BE-02: FastAPI, SSE y servicio de OCI Object Storage
├── tests/                        # Pruebas sin red ni LLM
├── scripts/
│   ├── test_pipeline_local.py    # Prueba E2E local IA-02 → IA-04
│   ├── validate_retrieval.py     # Validación IA-04 (Recall@4, Precision@4)
│   ├── comparar_chunking.py      # Compara extracción y chunking entre dos versiones (sin LLM)
│   └── run_pipeline_real.py      # Pipeline completo IA-02 → IA-08 con Gemini real
├── specs/                        # Especificaciones y ADRs (specs/nueva_mente/decisiones/)
├── .reports/                     # Reportes de validación
├── brain/                        # Plan de implementación y tareas
├── docs/                         # Registro de mejoras (MEJORAS_FASE_A.md)
├── pyproject.toml / uv.lock
├── requirements.txt              # Export compatible con pip
└── .env.example
```

---

## Instalación

Requisitos: Python **≥ 3.14** y [uv](https://docs.astral.sh/uv/) (recomendado) o `pip`.

```bash
git clone https://github.com/Fernando-Falla/NuevaMente_DataIA.git
cd NuevaMente_DataIA
uv sync
```

Con pip:

```bash
python -m venv .venv
source .venv/bin/activate  # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
```

La primera ejecución con embeddings locales descarga el modelo (~1 GB) en `.dataia_models/`.

## Variables de entorno

```bash
cp .env.example .env
```

Las mínimas:

```env
# Data/IA (ingestión, chunking, embeddings de Gemini)
GOOGLE_API_KEY=your_google_api_key_here
# Generación y juez (AI Core). Puede ser la misma clave.
GEMINI_API_KEY=your_google_api_key_here
# Opcional: modelo de Gemini (por defecto gemini-3.5-flash-lite)
# GEMINI_MODEL=gemini-3.5-flash-lite
# Opcional: Groq por etapa
# GROQ_API_KEY=your_groq_api_key_here
```

La lista completa (límites, ritmo, proveedores por etapa, embeddings y ChromaDB) está comentada en `.env.example`.

## Uso rápido

> **Redes con inspección TLS** (antivirus o proxy que reemplaza certificados): usa `uv sync --system-certs`. Los scripts usan `truststore` para confiar en los certificados del sistema.

```powershell
# Pruebas automáticas (sin red ni LLM)
uv run pytest

# Pipeline IA-02 → IA-04 (extracción, chunking estructural e inserción en ChromaDB)
uv run python scripts/test_pipeline_local.py "ruta\al\documento.pdf"

# Pipeline completo IA-02 → IA-08 con Gemini real
uv run --system-certs python scripts/run_pipeline_real.py "ruta\al\documento.pdf" Junior Flashcards General

# Validación del retrieval (requiere documentos ya ingestados)
uv run python scripts/validate_retrieval.py
```

Perfiles: `Junior`, `Senior`, `Ejecutivo`. Formatos: `Flashcards`, `"Quiz Interactivo"`, `"Resumen Ejecutivo"`, `"Mapa Mental"`. Los resultados se guardan en `.reports/`.

---

## API (BE-01 y BE-02)

El backend ejecuta el pipeline en el mismo proceso, sin microservicios intermedios.

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

- Swagger: `http://localhost:8000/docs`
- Health check: `GET /health`

### `POST /api/v1/adaptar-contenido` (multipart/form-data)

| Parámetro | Valores |
|---|---|
| `documento_original` | Archivo PDF, `.md` o `.txt` (máx. 25 MB) |
| `perfil_destinatario` | `Junior` (default), `Senior`, `Ejecutivo` |
| `formato_salida` | `Flashcards` (default), `Quiz Interactivo`, `Mapa Mental`, `Guia Paso a Paso`, `Resumen Ejecutivo` |
| `nicho_sector` | `TI`, `Fintech`, `Salud`, `Marketing digital`, `General` (default) |
| `nivel_detalle` | `Didactico` (default), `Tecnico Intermedio`, `Exhaustivo` |
| `documento_titulo` | Opcional; si se omite, se infiere del nombre del archivo |

| Respuesta | Significado |
|---|---|
| `200` | `AdaptacionResponseDTO`: contenido adaptado, metadatos, trazabilidad de chunks y validación de fidelidad |
| `400` | `DOMINIO_NO_SOPORTADO` o `ARCHIVO_INVALIDO` |
| `413` | `ARCHIVO_DEMASIADO_GRANDE` o `DOCUMENTO_DEMASIADO_EXTENSO` |
| `415` | Extensión no soportada |
| `422` | `FORMATO_NO_ADECUADO`, `FIDELIDAD_INSUFICIENTE` o archivo vacío |
| `503` | `ERROR_PROVEEDOR_LLM` (cuota agotada temporalmente) |

Con `OCI_STORAGE_ENABLED=true`, el backend guarda el archivo original y el JSON generado en OCI Object Storage y devuelve sus identificadores en `almacenamiento_oci`.

### `POST /api/v1/adaptar-contenido/stream` (SSE)

Mismos parámetros. Envía el progreso en tiempo real para que el frontend no espere a ciegas ni sufra timeouts en documentos extensos:

1. `event: telemetria`: etapas `EXTRACCION` (20 %), `INDEXACION` (40 %), `GENERACION` (60 %), `AUDITORIA` (80 %), `PERSISTENCIA` (95 %) y `COMPLETADO` (100 %).
2. `event: resultado`: el `AdaptacionResponseDTO` final.
3. `event: error`: `AdaptacionErrorResponseDTO` si el pipeline rechaza el documento.
4. `event: fin`: `{"status": "finalizado", "tiempo_total_segundos": ...}`.

---

## Estado de implementación

| Issue | Descripción | Estado |
|-|-|-|
| IA-01 | Setup y constitución | Completado |
| IA-02 | Ingestión, validación, normalización y metadata | Completado |
| IA-02b/c | Límites de tamaño, control de cuota y dominios | Completado |
| IA-03 | Chunking estructural + metadata | Completado |
| IA-04 | Embeddings + ChromaDB + validación | Completado |
| Fase A | Mejoras de IA-02 a IA-04 (`docs/MEJORAS_FASE_A.md`) | Completado |
| Proveedores | LLM por etapa (Gemini/Groq) y embeddings locales por defecto | Completado |
| IA-05 | Selección de contexto por cobertura | Completado |
| IA-06 | Generación en 5 formatos × 3 perfiles | Completado |
| IA-07 | Validación de fidelidad (juez por ítem) | Completado |
| IA-08 | Contrato JSON con el backend | Completado |
| BE-01 | Backend FastAPI unificado | Completado |
| BE-02 | Streaming SSE de progreso | Completado |

## Decisiones técnicas

Las decisiones que modifican la constitución se registran como ADR en `specs/nueva_mente/decisiones/`:

- **ADR-001:** cinco formatos de salida × tres perfiles. El formato apenas influye en el consumo de tokens: entre el 90 % y el 98 % es la entrada (fragmentos del documento).
- **ADR-002:** embeddings locales por defecto y proveedor de LLM por etapa (Gemini/Groq).

Otras:
- Extracción PDF con `import pymupdf` (no `fitz`, deprecado).
- El modelo de Gemini se cambia con `GEMINI_MODEL` sin tocar código: Google retira modelos para las claves nuevas (`gemini-2.5-flash` ya responde 404).
- Metadata pedagógica (conceptos, dificultad, prerrequisitos) a nivel de documento y de chunk, con caché local en `.dataia_cache/`.

## Integración con el repositorio del equipo

`src/nuevamente_ai/` proviene del AI Core del equipo (`nuevamente-ai-core/src/ai`, rama `feat/backend-ia-integration`, commit `c0fb82b`), adaptado para importar `dataia` directamente. `src/dataia/common/providers.py` también parte de ese commit, con clave y modelo configurables.

Monorepo del equipo: [No-Country-simulation/G10-LATAM-EQUIPO15](https://github.com/No-Country-simulation/G10-LATAM-EQUIPO15) (área Data/IA, carpeta `ia/`).

## Licencia y contexto

Proyecto del **Hackathon ONE G10 — Alura Latam / Oracle Next Education**, equipo G10-LATAM-EQUIPO15, squad Data & IA. Los PDF de prueba son de terceros y no se versionan.
