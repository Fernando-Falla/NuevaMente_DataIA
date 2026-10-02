# Arquitectura: Proyecto NuevaMente

## Visión General
NuevaMente es un pipeline de procesamiento de texto con RAG y RAG Avanzado diseñado específicamente para la generación de contenido educativo adaptado a partir de documentos técnicos.

## Flujo del Pipeline y Componentes
1. **Ingestión y Validación:** Maneja archivos de entrada en formato PDF, Markdown y TXT.
2. **Chunking y Metadatos:** Divide el texto manteniendo la coherencia semántica y el contexto, añadiendo metadatos relevantes para mejorar la recuperación.
3. **Embeddings y Vector Store:** Utiliza ChromaDB de forma local/persistente para almacenar los vectores multidimensionales.
4. **Retriever / RAG:** Motor de búsqueda semántica para recuperar el contexto más relevante.
5. **Generador LLM:** Integración de modelos base (Gemini, Claude o GPT) enfocados en realizar la adaptación pedagógica de los textos técnicos.
6. **Validación de Fidelidad:** Módulo evaluador para comprobar que el contenido adaptado no contenga alucinaciones y respete los hechos del documento original.
7. **Estructurador JSON:** Capa final de formateo que emite los datos estructurados en formato JSON para su posterior consumo por plataformas de e-learning.

## Stack Tecnológico
- **Lenguaje:** Python
- **Gestor de Paquetes/Entornos:** `uv`
- **Orquestación AI:** LangChain
- **Base de Datos Vectorial:** ChromaDB
- **Modelos (LLM):** Flexibilidad para Gemini, Claude y GPT.
