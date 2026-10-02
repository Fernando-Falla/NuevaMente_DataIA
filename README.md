# NuevaMente — Data & IA Pipeline

Pipeline de **ingestión → chunking → embeddings → vector store → retriever** para el proyecto **NuevaMente** (Hackathon ONE G10 / Alura Latam — Equipo 15).

Transforma documentación técnica (PDF, Markdown, TXT) en fragmentos trazables, semánticamente enriquecidos, listos para RAG y generación de contenido educativo adaptado.

> **Alcance actual:** IA-02, IA-03 e IA-04 completados (flujo local determinista y enriquecido por LLM).  
> **Pendiente:** IA-05 (Retriever), IA-06 (Generación LLM), IA-07 (Validación de fidelidad), IA-08 (Integración Backend / JSON de salida).

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

## Stack

|Componente|Tecnología|
|-|-|
|Lenguaje|Python ≥ 3.14|
|Gestor de entorno|[uv](https://github.com/astral-sh/uv)|
|Extracción PDF|PyMuPDF (`import pymupdf`)|
|Validación / DTOs|Pydantic v2|
|Enriquecimiento LLM|Gemini (`gemini-2.5-flash`) con Context Caching|
|Chunking|LangChain Text Splitters (Recursive, 800/150) + Custom Structural Splitter|
|Embeddings|Gemini (`models/gemini-embedding-001`)|
|Vector store|ChromaDB (persistente, colección `nuevamente_docs`)|
|Orquestación|LangChain|

Dependencias declaradas en `pyproject.toml` y exportadas en `requirements.txt`.

---

## Estructura del repositorio

```text
.
├── src/
│   └── dataia/                   # Core del pipeline
│       ├── ingestion/            # IA-02: Extracción y enriquecimiento de metadata
│       ├── chunking/             # IA-03: Splitter estructural y metadata por chunk
│       ├── vectorstore/          # IA-04: Cliente ChromaDB
│       └── common/               # Modelos Pydantic compartidos
├── scripts/
│   ├── test_pipeline_local.py    # Prueba E2E local IA-02→IA-04 (incluye auditoría visual)
│   └── validate_retrieval.py     # Validación IA-04 midiendo Recall@4 y Precision@4
├── brain/                        # Documentación viva (task.md, implementation_plan.md)
├── docs/                         # Documentación adicional de diseño
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

# Opcional: modelo de embeddings (default: models/gemini-embedding-001)
# GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001

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

### 1. Prueba Local del Pipeline (IA-02 → IA-04)

Ejecuta el pipeline completo hasta la base de datos vectorial, demostrando extracción, chunking estructural (protección de tablas/código) e inserción en ChromaDB.

Desde la **raíz** del proyecto:

```powershell
# Windows
$env:GOOGLE_API_KEY = "TU_API_KEY_REAL"
uv run python scripts/test_pipeline_local.py "ruta\al\documento.pdf"
```

### 2. Validación de Recuperación (IA-04)

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
|IA-05|Retriever / RAG|Pendiente|
|IA-06|Generación LLM + perfiles|Pendiente|
|IA-07|Validación de fidelidad|Pendiente|
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

Este paquete corresponde al área **Data/IA** del monorepo:

[https://github.com/No-Country-simulation/G10-LATAM-EQUIPO15](https://github.com/No-Country-simulation/G10-LATAM-EQUIPO15)

|Destino en el equipo|Rama de trabajo|
|-|-|
|Carpeta `ia/`|`dev-ia` (vía feature branch + PR)|

---

## Licencia / contexto

Proyecto desarrollado en el marco del **Hackathon ONE G10 — Alura Latam / Oracle Next Education**.  
Equipo: **G10-LATAM-EQUIPO15** — squad Data & IA.
