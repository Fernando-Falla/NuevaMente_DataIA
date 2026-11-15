# Plan de Implementación: NuevaMente (Data & IA Pipeline)

Este plan refleja estrictamente la "Constitución" del proyecto y el flujo detallado de las actividades **IA-01 a IA-08**.

## Principios Fundamentales
1. **Spec-Driven Development**: Alineación total con el flujo de Tareas y Constitución.
2. **Trazabilidad Total**: Conservación estricta de `document_id` → `chunk_id` → `fuente` en todo el pipeline.
3. **Contratos Explícitos**: Uso de `Pydantic v2` para validación de interfaces.
4. **Errores Controlados**: Retorno de objetos de estado tipados (`status`, `codigo`, `mensaje`) en lugar de excepciones crudas.
5. **Determinismo Local**: IA-02, IA-03 e IA-04 operan localmente para asegurar consistencia en el MVP.

## Estado Actual del Flujo del Pipeline
- **IA-01 - Setup & Constitution**: COMPLETADO. Stack Python 3.11+, uv, Pydantic, PyMuPDF, ChromaDB, Langchain.
- **IA-02 - Ingestión**: COMPLETADO (Reapertura). Extracción (PyMuPDF), validación técnica heurística, normalización y asignación de `document_id`. Se añadió extracción de metadata pedagógica a nivel documento con caché local (`gemini-2.5-flash`).
- **IA-03 - Chunking**: COMPLETADO (Reapertura). Implementación con RecursiveCharacterTextSplitter jerárquico (800 max / 150 overlap) preservando rígidamente `document_id`, `chunk_id`. Se agregó consciencia estructural (protección de código y tablas, asociación de encabezados) y metadata pedagógica a nivel chunk con LLM.
- **IA-04 - Embeddings**: COMPLETADO (Reapertura Parcial). Implementación con modelo `models/gemini-embedding-001` y persistencia en ChromaDB local. Pendiente la validación de recuperación con consultas representativas para medir Recall/Precision.
- **IA-05 - Retriever/RAG**: COMPLETADO. Selección de contexto por cobertura de secciones y tipos de contenido, respetando presupuesto de tokens y desempate por similitud semántica.
- **IA-06 - LLM + Adaptación**: COMPLETADO. Generación de los 5 formatos educativos (Flashcards, Quiz Interactivo, Mapa Mental, Guía Paso a Paso, Resumen Ejecutivo) calibrados para 3 perfiles (Junior, Senior, Ejecutivo).
- **IA-07 - Validación IA**: COMPLETADO. Evaluación de fidelidad ítem por ítem con Agente Crítico, cálculo de `anclaje_fuente_score` determinista y ciclo de reintentos estructurados.
- **IA-08 - Integración (JSON)**: COMPLETADO. DTOs de Request y Response tipados en Pydantic v2, serialización limpia UTF-8, reporte de trazabilidad/auditoría y exportación de JSON Schemas canónicos en `specs/nueva_mente/schemas/`.
- **BE-01 - Servidor Backend Unificado**: COMPLETADO. FastAPI en memoria/proceso (`POST /api/v1/adaptar-contenido`), validación multipart, DTOs Pydantic v2 y persistencia dual en OCI Object Storage con fallback resiliente.
- **BE-02 - Telemetría y Streaming SSE**: COMPLETADO. Endpoint `POST /api/v1/adaptar-contenido/stream` para streaming en tiempo real con eventos de progreso (`telemetria`) en las 5 etapas, artefacto final (`resultado`), control de errores tipados (`error`) y evento de cierre (`fin`).

## Decisiones Técnicas Aprobadas
> [!NOTE]
> - **LLM y Orquestación**: LangChain como orquestador modular con los imports modernos `langchain_text_splitters` y `langchain_chroma.Chroma`.
> - **Extracción PDF**: Actualizado a la sintaxis moderna usando el import `pymupdf` (evitando fitz deprecado).
> - **Modelo de Embeddings**: Cambio definitivo al modelo `models/gemini-embedding-001` de Gemini (evitando errores 404).
> - **Seguridad y Credenciales**: Inyección segura vía sesión activa de PowerShell (`$env:GOOGLE_API_KEY`), prescindiendo de archivos `.env` reales para maximizar la seguridad.
> - **Vector Store**: Persistencia en ChromaDB comprobada exitosamente en la colección por defecto `nuevamente_docs` dentro de `.chromadb_data/`. Las variables de entorno `CHROMADB_DIR` y `CHROMADB_COLLECTION` fueron añadidas para facilitar el despliegue Docker/OCI.
> - **Estructura de Directorios**: Migración completa a `src/dataia/` para respetar la Constitución del proyecto.

## Verification Plan
### Automated Tests
- Pruebas deterministas para IA-02: Documento válido, documento vacío, documento no técnico, formato no soportado.
- Pruebas para garantizar que los modelos Pydantic no validen datos incompletos.
### Pruebas de Flujo E2E
- Trazabilidad completa de `document_id` desde IA-02 hasta IA-08.
- **Prueba Local**: Implementado `scripts/test_pipeline_local.py` para validar la integración de IA-02, IA-03 y IA-04 aislando las dependencias del equipo de Backend.
- **Seguridad y Métricas**: Uso seguro de credenciales con `python-dotenv`. El script evalúa densidades tabulares (identificando pipes y tabulaciones) aislando muestras para auditar visualmente que el Chunking Jerárquico no destruya la estructura original de tablas.
