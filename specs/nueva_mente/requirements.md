# Requisitos: Proyecto NuevaMente

## Requisitos Funcionales
- **Ingestión Multi-Formato:** El sistema debe aceptar y procesar eficientemente archivos `.pdf`, `.md` y `.txt`.
- **Estrategias de Chunking:** Debe implementar división de texto por caracteres/tokens con superposición (overlap) y opcionalmente chunking semántico estructural.
- **Almacenamiento Vectorial:** Debe inicializar y gestionar colecciones en ChromaDB para almacenar embeddings.
- **Recuperación Avanzada:** Debe implementar un Retriever conectable a LangChain para extraer los *k* fragmentos más relevantes.
- **Adaptación Pedagógica:** El LLM debe procesar el texto técnico utilizando un prompt sistémico que simplifique y estructure el texto para estudiantes.
- **Validación de Contenido:** El sistema debe contrastar la salida generada con los fragmentos recuperados para evitar pérdida de fidelidad o invenciones.
- **Formato Estricto de Salida:** La respuesta final de la ejecución del pipeline debe ser un objeto JSON válido según un esquema predefinido.

## Requisitos No Funcionales
- **Modularidad:** El código debe estar fuertemente desacoplado. Cada paso del pipeline debe poder testearse por separado.
- **Reproducibilidad:** Gestión de dependencias y entornos virtualizados rápida y estrictamente mediante `uv`.
- **Escalabilidad:** El Vector Store debe ser capaz de manejar repositorios grandes de documentos educativos.
