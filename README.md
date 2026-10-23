# NuevaMente — Data & IA Pipeline

Pipeline de **ingestión → chunking → embeddings → vector store → retriever** para el proyecto **NuevaMente** (Hackathon ONE G10 / Alura Latam — Equipo 15).

Transforma documentación técnica (PDF, Markdown, TXT) en fragmentos trazables, semánticamente enriquecidos, listos para RAG y generación de contenido educativo adaptado.

> **Alcance actual:** IA-02 a IA-04 completados y mejorados (Fase A); IA-07 (validación de fidelidad) completado. La generación (IA-06) usa el AI Core del equipo adaptado en `src/nuevamente_ai/`.  
> **Pendiente:** IA-05 (selección de contexto por cobertura), IA-06 (uso de la metadata pedagógica), IA-08 (contrato JSON con el backend).

---

## Arquitectura del pipeline

```text
Documento (PDF / MD / TXT)
        │
        ▼
┌───────────────────┐
│  IA-02  Ingestión │  validación · extracción · normalización · document_id
│                   │  + Extracción Metadata Pedagógica (Gemini Flash)
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  IA-03  Chunking  │  splitter jerárquico consciente (protege código/tablas)
│                   │  + Metadata Pedagógica por chunk (Gemini Flash)
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  IA-04  Vector DB │  Gemini embeddings · ChromaDB persistente
│                   │  + Validación Recall/Precision (LLM-as-a-judge)
└───────────────────┘
```

**Principios:**

* Trazabilidad total: `document_id` → `chunk_id` → fuente
* Contratos explícitos con **Pydantic v2**
* Errores controlados (estado tipado, no excepciones crudas)
* Decisiones orientadas a **Generación Pedagógica**, no a Q&A conversacional libre.

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

Los rechazos ocurren antes de llamar al LLM. Las llamadas a Gemini respetan límites por minuto configurables, pensados para la cuenta gratuita, y ante un `429` esperan y reintentan. Detalle y mediciones: `specs/nueva_mente/ia02_tamano_y_cuota.md` y `.reports/ia02-tamano-y-dominios-2026-10-22.md`.

## Stack

|Componente|Tecnología|
|-|-|
|Lenguaje|Python ≥ 3.14|
|Gestor de entorno|[uv](https://github.com/astral-sh/uv)|
|Extracción PDF|PyMuPDF + `pymupdf4llm` (Markdown con títulos y secciones; respaldo a texto plano por página)|
|Validación / DTOs|Pydantic v2|
|Enriquecimiento LLM|Gemini (`gemini-3.1-flash-lite`, configurable con `GEMINI_MODEL`), clasificación de chunks en lotes, caché local|
|Chunking|LangChain Text Splitters (Recursive, 800/150) + Custom Structural Splitter sobre el documento completo (`page`, `page_end`, `section`)|
|Embeddings|Gemini (`models/gemini-embedding-001`)|
|Vector store|ChromaDB (persistente, colección `nuevamente_docs`, ids estables por `chunk_id`) + registro por documento|
|Pruebas|pytest (`tests/`)|
|Orquestación|LangChain|

Dependencias declaradas en `pyproject.toml` y exportadas en `requirements.txt`.

---

## Estructura del repositorio

```text
.
├── src/
│   ├── dataia/                   # Data/IA: IA-02 a IA-04
│   │   ├── ingestion/            # IA-02: Extracción y enriquecimiento de metadata
│   │   ├── chunking/             # IA-03: Splitter estructural y metadata por chunk
│   │   ├── vectorstore/          # IA-04: Cliente ChromaDB y registro por documento
│   │   └── common/               # Modelos Pydantic, credenciales y límites del proveedor
│   └── nuevamente_ai/            # Generación (IA-05 a IA-08): grafo LangGraph, agentes, prompts y schemas
│       └── agents/critico.py     # IA-07: juez de fidelidad por ítem
├── tests/
│   ├── test_dataia.py            # Pruebas sin red ni LLM de IA-02 a IA-04
│   ├── test_critico.py           # Pruebas del agente crítico (IA-07)
│   └── test_ai_core.py           # Pruebas del grafo y del pipeline completo (embeddings simulados)
├── scripts/
│   ├── test_pipeline_local.py    # Prueba E2E local IA-02→IA-04 (incluye auditoría visual)
│   ├── validate_retrieval.py     # Validación IA-04 midiendo Recall@4 y Precision@4
│   ├── comparar_chunking.py      # Compara extracción y chunking entre dos versiones (sin LLM)
│   └── run_pipeline_real.py      # Pipeline completo IA-02 → IA-08 con Gemini real
├── brain/                        # Documentación viva (task.md, implementation_plan.md)
├── docs/                         # Documentación de cambios (MEJORAS_FASE_A.md)
├── pyproject.toml / uv.lock      # Configuración de dependencias (uv)
├── requirements.txt              # Export compatible con pip
├── .env.example
└── README.md
```

---

## Instalación

### Requisitos

* Python **≥ 3.14**
* [uv](https://docs.astral.sh/uv/) instalado (recomendado) o `pip`.

### Pasos con uv

```bash
# Clonar / ubicarse en la raíz del proyecto
cd nuevamente-dataia-pipe

# Crear entorno e instalar dependencias
uv sync
```

### Pasos con pip tradicional

```bash
python -m venv .venv
source .venv/bin/activate  # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
```

---

## Variables de entorno

```bash
cp .env.example .env
```

Contenido esperado de `.env`:

```env
# Obligatoria para embeddings (IA-04) y extracción de metadata (IA-02/IA-03)
GOOGLE_API_KEY=your_google_api_key_here

# Opcional: clave propia para Data/IA (si falta, se usa GOOGLE_API_KEY)
# DATAIA_GOOGLE_API_KEY=your_google_api_key_here

# Opcional: modelo para la metadata pedagógica (default: gemini-3.1-flash-lite)
# GEMINI_MODEL=gemini-3.1-flash-lite

# Opcional: modelo de embeddings (default: models/gemini-embedding-001)
# GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001

# Opcional: con 1, un fallo del proveedor aborta en lugar de usar valores por defecto
# IA_STRICT_PROVIDERS=1

# Opcional: registro por documento, caché y tamaño de lote de clasificación
# DATAIA_DOCUMENTS_DIR=.dataia_documents
# DATAIA_CACHE_DIR=.dataia_cache
# DATAIA_ENRICH_BATCH_SIZE=15

# Opcional: límites de tamaño (se rechaza antes de llamar al LLM)
# DATAIA_MAX_FILE_MB=25
# DATAIA_MAX_PAGES=300
# DATAIA_MAX_DOCUMENT_TOKENS=150000
# DATAIA_DOC_METADATA_MAX_TOKENS=8000

# Opcional: control de ritmo (valores prudentes para la cuenta gratuita de Gemini)
# IA_PROVIDER_RPM=10
# IA_PROVIDER_TPM=200000
# IA_EMBEDDING_RPM=100
# IA_EMBEDDING_TPM=20000
# IA_PROVIDER_QUOTA_RETRIES=2
# DATAIA_EMBEDDING_BATCH_SIZE=20

# Opcional: persistencia ChromaDB
# CHROMADB_DIR=.chromadb_data
# CHROMADB_COLLECTION=nuevamente_docs
```

**Seguridad**

* Preferible definir la clave solo en la sesión de terminal:

```powershell
# Windows (PowerShell)
$env:GOOGLE_API_KEY = "TU_API_KEY_REAL"
```

```bash
# Linux / macOS
export GOOGLE_API_KEY="TU_API_KEY_REAL"
```

---

## Uso rápido y Pruebas

> **Redes con inspección TLS** (antivirus o proxy que reemplaza certificados): `uv` necesita `--system-certs` para descargar paquetes (`uv sync --system-certs`), y los scripts usan `truststore` para que Python confíe en los certificados del sistema al llamar a Gemini.

### 0. Pruebas automáticas (sin red ni LLM)

```powershell
uv run pytest
```

### 1. Prueba Local del Pipeline (IA-02 → IA-04)

Ejecuta el pipeline completo hasta la base de datos vectorial, demostrando extracción, chunking estructural (protección de tablas/código) e inserción en ChromaDB.

Desde la **raíz** del proyecto:

```powershell
# Windows
$env:GOOGLE_API_KEY = "TU_API_KEY_REAL"
uv run python scripts/test_pipeline_local.py "ruta\al\documento.pdf"
```

### 2. Pipeline completo con Gemini real (IA-02 → IA-08)

```powershell
uv run --system-certs python scripts/run_pipeline_real.py "ruta\al\documento.pdf" Junior Flashcards General
```

Perfiles: `Junior`, `Senior`, `Ejecutivo`. Formatos: `Flashcards`, `"Quiz Interactivo"`, `"Resumen Ejecutivo"`, `"Mapa Mental"`. La respuesta JSON se guarda en `.reports/`.

### 3. Validación de Recuperación (IA-04)

Una vez que tengas documentos ingestados en `.chromadb_data`, ejecuta la validación de Recall y Precision usando las 5 consultas representativas (utiliza LLM-as-a-judge):

```powershell
uv run python scripts/validate_retrieval.py
```

El reporte se guardará automáticamente en `.reports/`.

---

## Estado de implementación

|Issue|Descripción|Estado|
|-|-|-|
|IA-01|Setup & constitución|Completado|
|IA-02|Ingestión, validación, normalización, metadata|Completado|
|IA-03|Chunking jerárquico consciente + metadata|Completado|
|IA-04|Embeddings Gemini + ChromaDB + Validación|Completado|
|Fase A|Mejoras de IA-02 a IA-04 (ver `docs/MEJORAS_FASE_A.md`)|Completado|
|IA-05|Retriever / RAG|Pendiente|
|IA-06|Generación LLM + perfiles|Pendiente|
|IA-02b/c|Límites de tamaño, control de cuota y dominios TI, Fintech, Salud y Marketing digital|Completado|
|IA-07|Validación de fidelidad (juez por ítem, ver `.reports/ia07-validacion-fidelidad-2026-10-22.md`)|Completado|
|IA-08|Integración Backend (JSON contrato)|Pendiente|

Detalle de avance y tareas: `brain/implementation_plan.md`, `brain/task.md`.

---

## Decisiones técnicas relevantes

* Extracción PDF con `import pymupdf` (no `fitz` deprecado).
* **Chunking Estructural**: Extiende `RecursiveCharacterTextSplitter` para proteger bloques de código (\`\`\`) y tablas Markdown antes del corte, previniendo pérdida de contexto semántico.
* **Metadata Pedagógica**: Tanto a nivel documento como a nivel chunk, se utiliza `gemini-2.5-flash` con caché local en `.dataia_cache/` para extraer conceptos, nivel de dificultad y prerrequisitos (habilitando IA-06).
* Embeddings: `models/gemini-embedding-001` (evita 404 del modelo anterior).
* Vector store: Chroma vía `langchain-chroma`, configurable vía variables de entorno para Docker/OCI.

---

## Integración con el repositorio del equipo

`src/nuevamente_ai/` proviene del AI Core del equipo (`nuevamente-ai-core/src/ai`, rama `feat/backend-ia-integration`, commit `c0fb82b`), adaptado para importar `dataia` directamente. Cambios locales: crítico por ítem (IA-07), corrección del auditor y pruebas con embeddings simulados. `src/dataia/common/providers.py` también proviene de ese commit, con clave y modelo configurables.

Este paquete corresponde al área **Data/IA** del monorepo:

[https://github.com/No-Country-simulation/G10-LATAM-EQUIPO15](https://github.com/No-Country-simulation/G10-LATAM-EQUIPO15)

|Destino en el equipo|Rama de trabajo|
|-|-|
|Carpeta `ia/`|`dev-ia` (vía feature branch + PR)|

---

## Licencia / contexto

Proyecto desarrollado en el marco del **Hackathon ONE G10 — Alura Latam / Oracle Next Education**.  
Equipo: **G10-LATAM-EQUIPO15** — squad Data & IA.
