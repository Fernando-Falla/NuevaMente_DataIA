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
- [x] **Fase A: Mejoras de IA-02 a IA-04** (detalle en `docs/MEJORAS_FASE_A.md`)
  - [x] Extracción PDF a Markdown con `pymupdf4llm`, control de cobertura por página y limpieza de encabezados, pies y enlaces.
  - [x] `document_id` por hash del archivo (reingestión idempotente).
  - [x] Chunking sobre el documento completo con `page`, `page_end` y `section`.
  - [x] Clasificación de chunks en lotes, con caché por hash del texto y modelo configurable (`GEMINI_MODEL`).
  - [x] ChromaDB con ids estables, actualización de metadata sin recalcular embeddings y registro por documento.
  - [x] 15 pruebas automáticas sin red ni LLM en `tests/test_dataia.py`; validación con Gemini real sobre los PDFs de VCN, JWT y microservicios.
- [x] **Fase A2: Tamaño, cuota y dominios** (specs `ia02_tamano_y_cuota.md` e `ia02_dominios.md`)
  - [x] Límites de archivo, páginas y tokens antes de llamar al LLM.
  - [x] Metadata del documento a partir de un resumen acotado (8.000 tokens).
  - [x] Control de ritmo por minuto, espera ante 429 y embeddings por lotes de tokens.
  - [x] Detección de dominio (TI, Fintech, Salud, Marketing digital) con léxico de respaldo; nichos actualizados.
  - [x] Perfiles, consulta y contenido de contingencia neutrales; pautas por dominio.
  - [x] Validación real: `.reports/ia02-tamano-y-dominios-2026-10-22.md`.
  - [x] Validar con documentos reales de Fintech, Salud y Marketing digital (6 documentos; ver `tests/fixtures/documentos_reales.md`).
- [x] **Fase A3: Proveedores y embeddings** (spec `ia_proveedores_y_embeddings.md`)
  - [x] Proveedor de LLM por etapa (Gemini/Groq) con respaldo en Gemini y desvío por tamaño de prompt.
  - [x] Crítico en Groq validado (CA1–CA3 de IA-07).
  - [x] Embeddings locales (fastembed, mpnet) por defecto tras compararlos con Gemini.
  - [x] Validación con 6 documentos reales de Salud, Fintech y Marketing digital.
  - Reporte: `.reports/proveedores-y-embeddings-2026-10-22.md`.
- [ ] **Fase 5: Recuperación (IA-05)**
  - [ ] Selección de contexto por cobertura (sección y `tipo_contenido`) con `get_document_chunks`; la similitud queda como apoyo.
- [ ] **Fase 6: Generación LLM (IA-06)**
  - [ ] Prompt System y perfiles educativos.
  - [ ] Generación de Formatos (Quiz, Flashcards, etc).
- [x] **Fase 7: Validación de Fidelidad (IA-07)** (spec `specs/nueva_mente/ia07_validacion_fidelidad.md`)
  - [x] Comprobación contra fuentes: juez LLM con veredicto por ítem; score calculado en código.
  - [x] Recursos didácticos (analogías, `pista_didactica`) admitidos si no introducen datos falsos; distractores de quiz excluidos.
  - [x] Lógica de reintentos controlados con retroalimentación por ítem (máximo 2 intentos).
  - [x] Validación con Gemini real: `.reports/ia07-validacion-fidelidad-2026-10-22.md`.
- [ ] **Fase 8: Integración Backend (IA-08)**
  - [ ] Exportación de JSON estricto y compatible.

- [x] **Fase de Pruebas Unitarias/Integración (Local)**
  - [x] Crear entorno de prueba `scripts/test_pipeline_local.py`.
  - [x] Simular Backend y verificar trazabilidad de IA-02 a IA-04.
  - [x] **Seguridad y Auditoría:** Implementar `python-dotenv`, crear `.env.example` y asegurar `.gitignore`.
  - [x] **Métricas de Segmentación:** Evaluar tamaño de chunks, densidad tabular y aislar muestras para auditoría visual.
