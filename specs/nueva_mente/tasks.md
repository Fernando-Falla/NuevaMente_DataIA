# Plan de Tareas: Proyecto NuevaMente (SpecKit)

## Fase 1: Configuración
- TSK-01: Inicializar el proyecto Python utilizando `uv` y definir la estructura base de directorios (`src/`, `tests/`).
- TSK-02: Instalar dependencias principales (LangChain, ChromaDB, PyPDF, etc.).

## Fase 2: Núcleo (Core)
- TSK-03: Desarrollar módulo de Ingestión y Validación de documentos (Soporte para PDF, MD, TXT).
- TSK-04: Desarrollar módulo de Chunking y extracción de Metadatos.
- TSK-05: Configurar modelo de Embeddings e integrar ChromaDB (Vector Store).
- TSK-06: Implementar el Retriever (RAG básico/avanzado).

## Fase 3: Integración
- TSK-07: Desarrollar cadena LLM (Generador) con el prompt de adaptación pedagógica.
- TSK-08: Implementar módulo de validación de fidelidad (LLM-as-a-judge o similar).

## Fase 4: Pulido
- TSK-09: Configurar la salida estructurada garantizando un JSON válido.
- TSK-10: Crear script orquestador del pipeline completo (End-to-End).
- TSK-11: Desarrollar pruebas e iterar sobre resultados.
