# Tareas - NuevaMente (Data & IA)

## Fases de la Tarea (IA-01 a IA-08)
- **Fase 1: Setup y Constitución** (IA-01)
- **Fase 2: Ingestión Documental** (IA-02)
- **Fase 3: Segmentación y Contexto** (IA-03)
- **Fase 4: Vectorización** (IA-04)
- **Fase 5: Recuperación (RAG)** (IA-05)
- **Fase 6: Generación LLM** (IA-06)
- **Fase 7: Validación de Fidelidad** (IA-07)
- **Fase 8: Integración Backend** (IA-08)

## Dependencias de la tarea
- Flujo puramente secuencial: IA-02 -> IA-03 -> IA-04 -> IA-05 -> IA-06 -> IA-07 -> IA-08.
- [P] La definición de los prompts de adaptación pedagógica se puede realizar en paralelo a IA-04/05.

## Flujo de ejecución
1. Recibir documento.
2. Validar técnica y extraer texto -> Generar Metadata.
3. Segmentar con superposición (Chunking).
4. Guardar en ChromaDB (Embeddings).
5. Recuperar chunks mediante Similitud >= 0.75.
6. LLM Adapta para Perfil/Formato (Flashcard, Quiz, etc.).
7. Validador evalúa `anclaje_fuente_score`.
8. Formato final JSON.

## Lista de Verificación
- [x] **Fase 1: Setup (IA-01 & Constitution)**
  - [x] Inicializar `uv` e instalar LangChain, ChromaDB, PyMuPDF, Pydantic.
  - [x] Establecer estructura de carpetas `src/dataia/`.
- [x] **Fase 2: Ingestión Documental (IA-02)**
  - [x] Implementar contratos Pydantic v2.
  - [x] Crear validador de pertinencia técnica (determinista).
  - [x] Implementar normalización limpia de texto.
  - [x] Orquestador de ingesta con manejo controlado de errores y generación de `document_id`.
  - [x] [Reapertura] Extraer metadata pedagógica a nivel documento (IA-02.14 a IA-02.17).
  - [ ] [Reapertura] Pruebas con 3 documentos técnicos + 1 no técnico (IA-02.18).
- [x] **Fase 3: Segmentación y Contexto (IA-03)**
  - [x] Chunking jerárquico estricto (800 max / 150 overlap).
  - [x] Preservación crítica de trazabilidad (`document_id` -> `chunk_id` y metadata).
  - [x] [Reapertura] Consciencia estructural: no partir código ni tablas y asociar encabezados (IA-03.10 a IA-03.13).
  - [x] [Reapertura] Metadata pedagógica por chunk usando LLM (IA-03.14).
  - [ ] [Reapertura] Pruebas con documento técnico con código y tablas (IA-03.15).
- [x] **Fase 4: Vectorización (IA-04)**
  - [x] Configurar Gemini Embeddings (`langchain-google-genai`).
  - [x] Configurar persistencia en ChromaDB local preservando trazabilidad (configurable por variables de entorno `CHROMADB_DIR` y `CHROMADB_COLLECTION`).
  - [ ] [Reapertura] Validar recuperación con consultas representativas y medir Recall/Precision (IA-04.10 a IA-04.14).
- [ ] **Fase 5: Recuperación (IA-05)**
  - [ ] Retriever Semántico y evaluación del umbral de RAG.
- [ ] **Fase 6: Generación LLM (IA-06)**
  - [ ] Prompt System y perfiles educativos.
  - [ ] Generación de Formatos (Quiz, Flashcards, etc).
- [ ] **Fase 7: Validación de Fidelidad (IA-07)**
  - [ ] Comprobación contra fuentes.
  - [ ] Lógica de reintentos controlados.
- [ ] **Fase 8: Integración Backend (IA-08)**
  - [ ] Exportación de JSON estricto y compatible.

- [x] **Fase de Pruebas Unitarias/Integración (Local)**
  - [x] Crear entorno de prueba `scripts/test_pipeline_local.py`.
  - [x] Simular Backend y verificar trazabilidad de IA-02 a IA-04.
  - [x] **Seguridad y Auditoría:** Implementar `python-dotenv`, crear `.env.example` y asegurar `.gitignore`.
  - [x] **Métricas de Segmentación:** Evaluar tamaño de chunks, densidad tabular y aislar muestras para auditoría visual.
