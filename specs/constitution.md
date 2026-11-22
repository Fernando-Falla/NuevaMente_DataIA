# Constitution — NuevaMente · Data & IA Pipeline

**Proyecto:** NuevaMente – Sistema Inteligente de Adaptación y Generación de Contenido Educativo  
**Hackathon:** ONE G10 – Alura / Oracle  
**Ámbito:** Pipeline de Data & IA (IA-02 → IA-08)  
**Owner principal de IA-02 / IA-03 / IA-04:** Fernando Falla (Data Engineer)  
**Fecha de creación:** 2026-09-21

---

## 1. Principios Fundamentales

1. **Spec-Driven Development**  
   Todo feature se define primero en una Spec clara. La implementación solo comienza después de Plan + Tasks aprobados.

2. **Trazabilidad total**  
   Todo dato que fluye por el pipeline debe mantener la cadena:

document_id → chunk_id → embedding → contexto recuperado → contenido generado → fuente

Nunca se pierde el origen.

3. **Contratos explícitos y tipados**  
Todas las interfaces entre etapas usan modelos Pydantic v2.  
Entrada y salida de cada etapa están formalizadas y versionadas.

4. **Determinismo y testabilidad**  
IA-02, IA-03 e IA-04 deben ser lo más deterministas y locales posibles.  
Los tests unitarios e de integración son obligatorios y se escriben junto con el código.

5. **Separación de responsabilidades**  
- IA-02 → Ingestión + validación + normalización  
- IA-03 → Chunking + metadata  
- IA-04 → Embeddings + Vector Store  
- IA-05 → Retriever / RAG  
- IA-06 → LLM + Adaptación pedagógica  
- IA-07 → Validación de fidelidad  
- IA-08 → Integración + JSON final  

6. **Mínima dependencia de red en el camino crítico de IA-02/03/04**  
- IA-02 y IA-03: 100 % locales.  
- IA-04: solo se permite la llamada a Gemini Embeddings (con fallback local).  
- Vector Store: ChromaDB local y persistente durante desarrollo y pruebas.

7. **Errores controlados**  
Nunca se lanzan excepciones no capturadas hacia capas superiores.  
Todos los fallos se devuelven como objetos de error tipados con código y mensaje claro.

8. **Código limpio y mantenible**  
- Tipado estricto (Python 3.11+ + Pydantic v2)  
- Funciones pequeñas y con responsabilidad única  
- Nombres descriptivos  
- Sin side-effects ocultos  
- Documentación mínima pero suficiente (docstrings en funciones públicas)

---

## 2. Stack Técnico Oficial (MVP)

| Capa                    | Tecnología oficial                          | Notas       |
|-------------------------|---------------------------------------------|-------      |
| Lenguaje                | Python 3.11+ (entorno actual: 3.14)         | -           |
| Tipado / Validación     | Pydantic v2                                 | Obligatorio |
| Gestión de dependencias | uv + pyproject.toml                         | -           |
| Extracción PDF          | PyMuPDF (`pymupdf`) + `pymupdf4llm`         | Primario. Enmienda ADR-002 |
| Chunking                | LangChain RecursiveCharacterTextSplitter    | 800 tokens / 150 overlap (inicial) |
| Embeddings              | Locales (fastembed, `paraphrase-multilingual-mpnet-base-v2`) | Por defecto; Gemini `gemini-embedding-001` opcional. Enmienda ADR-002 |
| Vector Store            | ChromaDB (persistente local)                | Migración a OCI evaluada después |
| Orquestación posterior  | LangGraph                                   | Responsabilidad de IA-05/06 |

---

## 3. Estructura de Carpetas Oficial

```text
src/dataia/
├── common/
│   ├── ids.py
│   ├── models.py          # modelos compartidos
│   ├── exceptions.py
│   └── logging.py
├── ingestion/             # IA-02
│   ├── extractors/
│   ├── normalizer.py
│   ├── validators.py
│   ├── metadata.py
│   └── service.py
├── chunking/              # IA-03
│   ├── splitter.py
│   ├── metadata.py
│   └── service.py
├── embeddings/            # IA-04
│   ├── embedder.py
│   ├── vector_store.py
│   └── service.py
└── ...
tests/
├── ingestion/
├── chunking/
├── embeddings/
└── fixtures/

## 4. Reglas de Calidad

-Toda función pública tiene type hints completos y docstring.
-Cobertura de tests mínima objetivo: 80 % en módulos de IA-02, IA-03 e IA-04.
-Los fixtures de prueba deben incluir documentos reales (VCN OCI, JWT, Microservicios) y casos negativos.
-Ningún módulo de IA-02/03/04 importa código de IA-06 o superior.
-Los cambios de parámetros de chunking o embeddings deben registrarse en la Spec correspondiente.

## 5. 5. Flujo de Trabajo Obligatorio (por feature)

/speckit-specify
/speckit-plan
/speckit-tasks
/speckit-implement (tarea por tarea)
/speckit-checklist
/speckit-converge

La Constitution se aplica a todo el pipeline.

Cada feature (IA-02, IA-03, IA-04…) tiene su propio ciclo Spec → Plan → Tasks → Implement.

## 6. Decisiones de Diseño Ya Acordadas

Vector Store local (ChromaDB) durante desarrollo y pruebas.
Posible migración posterior a OCI Always Free.
DataIA no expone FastAPI propia. Expone funciones internas limpias.
Backend es el responsable de recibir el archivo y guardarlo en OCI.
Perfiles MVP: Principiante/Junior · Líder Técnico · Gestor Ejecutivo.
Formatos MVP: Flashcards · Quiz Interactivo · Resumen Ejecutivo (TL;DR) · Mapa Mental · Guía Paso a Paso (enmienda ADR-001).

## 7. Registro de Enmiendas

| Fecha | Sección | Cambio | Decisión |
|---|---|---|---|
| 2026-10-22 | §6 Formatos MVP | De 3 a 5 formatos: se agregan Mapa Mental y Guía Paso a Paso | `specs/nueva_mente/decisiones/ADR-001-cinco-formatos-de-salida.md` |
| 2026-10-22 | §2 Stack | Embeddings locales por defecto (Gemini opcional); extracción con `pymupdf4llm`; proveedor de LLM por etapa (Gemini/Groq) | `specs/nueva_mente/decisiones/ADR-002-embeddings-locales-y-proveedor-por-etapa.md` |
