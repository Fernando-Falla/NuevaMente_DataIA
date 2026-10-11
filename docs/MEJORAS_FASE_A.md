# Mejoras de Data/IA — Fase A: ingestión, chunking y vector store

**Alcance:** módulos `src/dataia/` (ingestión, chunking, embeddings y ChromaDB).

> Este documento se redactó para el repositorio del equipo (`No-Country-simulation/G10-LATAM-EQUIPO15`, rama `feat/dataia-fase-a`). Allí el paquete vive en `ia/src/dataia/`, las pruebas en `ia/tests/` y los scripts en `ia/scripts/`; en este repositorio son `src/dataia/`, `tests/` y `scripts/`. Las secciones sobre Docker y archivos compose aplican solo al repositorio del equipo. Los cambios hechos después en este repositorio están en la §10.
**Versión anterior:** commit `12ee492` de `feat/backend-ia-integration`.
**Estado:** implementado y probado localmente sin Docker, incluido Gemini real. La imagen Docker todavía no se validó (ver §7).

---

## 1. Propósito del pipeline y criterio de evaluación

El pipeline no responde preguntas sobre los documentos: **genera contenido adaptado** (flashcards, quiz, resumen ejecutivo, mapa mental) para un perfil (Junior, Senior, Ejecutivo) y un nicho. Por eso, la calidad de Data/IA se mide por:

- **Cobertura:** que el texto del documento llegue completo a los chunks.
- **Estructura:** que cada chunk sepa a qué sección y páginas pertenece.
- **Reutilización:** que un documento se ingiera una vez y sirva para generar varios formatos y perfiles.

## 2. Diagnóstico

Flujo actual: Backend → HTTP → servicio IA (`ia/src/ia_http`) → `ejecutar_pipeline_adaptacion` (`nuevamente-ai-core/src/ai/pipeline.py`) → ingestión → chunking → vector store → búsqueda → LangGraph.

**Base de `ia/`:** es correcta y se conserva. Tiene contratos Pydantic con estado `aprobado`/`rechazado`, trazabilidad (`document_id`, `chunk_id`, `page`), validación previa del documento, splitter con separadores por título, protección de código y tablas, y metadata pedagógica.

**Problemas encontrados en `ia/` (resueltos en esta fase):**

| Problema | Efecto |
|---|---|
| PDF extraído como texto plano | Sin títulos ni tablas: las protecciones del splitter estructural no se activaban con PDFs y `section` nunca se llenaba. |
| Chunking página por página | Un concepto que cruza de página quedaba partido sin solapamiento. |
| `document_id` aleatorio | Vectores duplicados al reingerir un documento y caché de enriquecimiento nunca reutilizada. |
| Una llamada al LLM por chunk | Costo y latencia proporcionales al número de chunks. |
| Normalizador | Aplastaba la indentación del código y de las listas anidadas. |
| Detección de títulos | Los comentarios `#` dentro de bloques de código se tomaban como títulos. |
| Metadata pedagógica del documento | No se persistía: solo vivía en memoria durante la petición. |

**Problemas fuera de `ia/` (Fases B y C, sin cambios aquí):**

- La etapa de generación usa `similarity_search(k=5)` con una consulta genérica: un patrón de preguntas y respuestas que entrega unos 4.000 tokens de documentos de decenas de páginas.
- La `pedagogical_metadata` y la metadata por chunk (`tipo_contenido`, `nivel_dificultad`) no llegan a los agentes.
- El agente crítico mide coincidencia léxica, no fidelidad. En el reintento inyecta al generador cinco palabras arbitrarias de la fuente, lo que induce contenido forzado.

`chunking/splitter.py` no se usa: lo reemplazó `structural_splitter.py`, que aplica la misma configuración (800 tokens, solapamiento de 150, mismos separadores) y agrega protección de bloques y títulos. No usarlo no causaba pérdida de información.

## 3. Cambios realizados

| Área | Cambio | Archivo |
|---|---|---|
| Extracción PDF | Markdown por página con `pymupdf4llm` (títulos, listas, código), con niveles de título calculados una vez por documento. | `ingestion/service.py` |
| Control de cobertura | Si el Markdown de una página conserva menos del 90 % de las palabras del texto plano, esa página se extrae con PyMuPDF. | `ingestion/service.py` |
| Limpieza | Los enlaces `[texto](url)` se reducen a `texto`. Se eliminan los encabezados y pies que aparecen en el 60 % o más de las páginas (solo en las 3 primeras y 3 últimas líneas de cada página; solo puede variar el contador de página). | `ingestion/service.py` |
| Identidad | `document_id = "doc-" + sha256(archivo)[:16]`. Parámetro opcional `document_name` para conservar el nombre original. | `ingestion/service.py` |
| Normalización | Conserva la indentación inicial y no altera el interior de los bloques de código. | `ingestion/normalizer.py` |
| Chunking | Se segmenta el documento completo con un mapa de páginas. Cada chunk registra `page`, `page_end` y `section`. Se descartan los chunks que solo contienen un título; los siguientes ya lo llevan antepuesto. | `chunking/structural_splitter.py` |
| Enriquecimiento | Clasificación en lotes de 15 chunks por llamada. Caché indexada por hash del texto. Si el LLM omite un chunk del lote, se reintenta solo ese. `tipo_contenido` restringido a los 6 valores válidos. | `chunking/structural_splitter.py` |
| Vector store | `chunk_id` como id del vector. Si el documento ya está indexado con los mismos fragmentos no se recalculan embeddings; si cambió, se reemplazan sus vectores. | `vectorstore/client.py` |
| Registro del documento | `pedagogical_metadata`, nombre, número de chunks y secciones en `DATAIA_DOCUMENTS_DIR/<document_id>.json`. | `vectorstore/client.py`, `vectorstore/service.py` |
| Lectura para generación | `get_document_chunks(document_id)` (todos los chunks en orden) y `load_document_record(document_id)`. Quedan listas para la Fase B; nadie las usa todavía. | `vectorstore/client.py` |
| Persistencia | Volumen `ia-data` en `/workspace/data` para ChromaDB, registro y cachés. | `ia/compose.http.yaml`, `compose.integration.yaml`, `ia/docker/Dockerfile.http` |
| Dependencias | `pymupdf4llm>=0.0.17,<1.0`. | `ia/requirements-tests.txt` |
| Credenciales | `DATAIA_GOOGLE_API_KEY` (opcional): clave propia para ingestión, chunking y embeddings, con respaldo en `GOOGLE_API_KEY`. Permite separar la cuota de Data/IA de la de AI Core. | `common/credentials.py`, archivos compose |

### Hallazgo durante la validación

Las páginas web impresas a PDF (los tres PDFs de prueba lo son) tienen imágenes y gráficos de fondo. Con su configuración por defecto, `pymupdf4llm` **descarta el texto superpuesto a ellos**. En "VCN y subredes" conservaba 458 de 5.825 palabras. Por eso:

- se extrae con `ignore_images=True` e `ignore_graphics=True`, que recupera el 100 % del texto. El costo es que las tablas dibujadas con líneas quedan como texto, sin formato de tabla;
- se agregó el control de cobertura por página, para que una pérdida así no pase inadvertida con otros PDFs o versiones de la librería.

## 4. Mediciones antes / después

Medido sin LLM con `ia/scripts/comparar_chunking.py` sobre los PDFs de `nuevamente-ai-core/tests/`. La cobertura es la proporción de palabras distintas del texto plano de PyMuPDF que aparecen en los chunks.

| Documento | Versión | Títulos detectados | Chunks | Chunks con `section` | Chunks que cruzan página | Cobertura |
|---|---|---|---|---|---|---|
| Arquitectura de microservicios (7 págs.) | anterior | 0 | 7 | 0 | 0 | 100 % |
| | nueva | 5 | 5 | 4 | 4 | 97,5 % |
| JWT en OCI (8 págs.) | anterior | 0 | 8 | 0 | 0 | 100 % |
| | nueva | 7 | 9 | 8 | 6 | 100 % |
| VCN y subredes (22 págs.) | anterior | 0 | 22 | 0 | 0 | 100 % |
| | nueva | 35 | 14 | 13 | 13 | 100 % |

- En la versión anterior, los chunks coincidían con las páginas: ningún chunk sabía a qué sección pertenecía.
- El 2,5 % que falta en "Arquitectura de microservicios" corresponde a la URL del pie de página, que se elimina a propósito. Una página que solo contenía el pie queda vacía y se descarta, por eso figuran 6 páginas con contenido.
- El total de palabras en chunks crece entre 3 % y 5 % por los títulos antepuestos y el solapamiento.
- Con 15 chunks por llamada, el enriquecimiento de "VCN y subredes" pasa de 22 llamadas al LLM a 1.

## 5. Compatibilidad

- Los contratos Pydantic solo agregan campos opcionales: `ChunkMetadata.page_end`, `ChunkingResult.pedagogical_metadata` y `VectorStoreResult.already_indexed`. `nuevamente-ai-core` funciona sin cambios.
- `insert_chunks` devuelve `bool` (si el documento ya estaba indexado) en lugar de `int`. Su único consumidor, `vectorstore/service.py`, está actualizado.
- El formato de `document_id` pasa de `doc-xxxxxxxx` (aleatorio) a `doc-` más 16 caracteres hexadecimales (hash). Los vectores indexados con la versión anterior no se reutilizan.

## 6. Configuración

| Variable | Defecto local | Docker | Uso |
|---|---|---|---|
| `DATAIA_GOOGLE_API_KEY` | sin definir | vacía salvo que se defina en `ia/.env` | Clave de Gemini solo para Data/IA; si falta, se usa `GOOGLE_API_KEY` |
| `CHROMADB_DIR` | `./.chromadb_data` | `/workspace/data/chromadb` | Persistencia de ChromaDB |
| `DATAIA_DOCUMENTS_DIR` | `./.dataia_documents` | `/workspace/data/documents` | Registro por documento |
| `DATAIA_CACHE_DIR` | `./.dataia_cache` | `/workspace/data/cache` | Caché del enriquecimiento |
| `DATAIA_ENRICH_BATCH_SIZE` | `15` | `15` | Chunks por llamada al LLM |
| `IA_STRICT_PROVIDERS` | sin definir | `1` | Con `1`, un fallo del LLM aborta; sin definir, se usan valores por defecto |

## 7. Pruebas y verificación

**Entorno local:** `.venv/`, creado con el Python 3.13 de Anaconda (`C:\ProgramData\anaconda3`) e instalado con pip. `conda create` falla en esta máquina por verificación SSL contra repo.anaconda.com. Comandos en `ia/README.md`.

| Verificación | Resultado |
|---|---|
| `ia/tests/test_dataia.py` (13 pruebas nuevas, sin red ni LLM) | 13 pasan |
| Suite de la etapa `tests` del Dockerfile (`ia/tests` + `test_ai_pipeline.py` + `test_critic_context.py`, mismo filtro `-k`) con la disposición de carpetas del contenedor | 61 pasan, 4 excluidas |
| Las 4 pruebas de extremo a extremo excluidas | Mismo resultado con la versión anterior y la nueva: 1 pasa y 3 fallan |

Las 3 pruebas de extremo a extremo fallan por un problema previo: el mock de embeddings parchea `src.dataia.vectorstore.client`, pero el servicio importa `dataia.vectorstore.client`, de modo que se llama a Gemini real con una clave ficticia.

### Validación con Gemini real

Equivalente local de `ia/compose.real.yaml`: `gemini-3.1-flash-lite`, `gemini-embedding-001` e `IA_STRICT_PROVIDERS=1`.

**Clasificación de chunks ("JWT en OCI", 9 chunks).** Gemini clasificó los 9 en un lote. Ejemplos:

| Chunk | Páginas | Sección | Tipo | Dificultad | Concepto principal |
|---|---|---|---|---|---|
| 0002 | 1–2 | Validación de tokens para agregar autenticación… | definicion | 3 | Validación de tokens en API Gateway |
| 0003 | 2–3 | ¿Qué sucede durante la autenticación de token? | procedimiento | 4 | Proceso de autenticación de tokens y políticas de validación |
| 0006 | 5–6 | Notas sobre los tokens web JSON (JWT) | definicion | 3 | Estructura y validación de JSON Web Tokens (JWT) |
| 0008 | 7–8 | Notas sobre la protección contra… (CSRF) | codigo | 5 | Protección contra ataques CSRF y transformación de cabeceras |

El registro del documento guardó 8 conceptos clave, 4 prerrequisitos, el resumen ejecutivo y las 6 secciones.

**Etapas de Data/IA ("VCN y subredes", 14 chunks).** Se midieron dos ingestiones seguidas del mismo archivo:

| | Ingestión | Chunking + clasificación | Vector store | Llamadas de clasificación |
|---|---|---|---|---|
| Primera | 9,3 s | 30,4 s | 4,3 s | 1 lote + 1 reintento individual (Gemini omitió 1 chunk del lote) |
| Segunda (mismo archivo) | 0,9 s | 0,0 s | 2,3 s (`already_indexed=True`) | 0 |

La versión anterior habría hecho 22 llamadas, una por página, y repetido todo en cada ingestión.

**Pipeline completo ("JWT en OCI", Junior, Flashcards).**

| Versión | Hasta iniciar la generación | Resultado |
|---|---|---|
| anterior (2 ejecuciones) | 73 s y 172 s | 422 "Contexto Insuficiente" (score 0,78 y 0,79, umbral 0,85) |
| nueva (desde cero) | 19 s | 422 "Contexto Insuficiente" (score 0,78) |

Con las dos versiones, el agente crítico rechaza un documento pertinente. La causa no está en Data/IA: es la métrica léxica del crítico (§2), que corresponde a la Fase C. En la primera ejecución, la generación también falló una vez con `503 UNAVAILABLE` de Gemini (alta demanda del modelo, error temporal).

**Notas del entorno local:**
- Python necesita `truststore` (`truststore.inject_into_ssl()`) para verificar los certificados con el almacén de Windows; sin eso, las llamadas a Gemini fallan con `CERTIFICATE_VERIFY_FAILED`.
- La versión anterior guarda su caché en rutas relativas que, en directorios profundos, superan el límite de 260 caracteres de Windows.

**No verificado todavía:** la construcción y ejecución de la imagen Docker (Python 3.14).

## 8. Limitaciones conocidas

- Las tablas de los PDF quedan como texto, sin formato de tabla.
- El servicio HTTP guarda el archivo como `documento.<ext>` y todavía no pasa `document_name`, así que el nombre registrado es el temporal.
- AI Core importa `src.dataia` y Data/IA importa `dataia`: el mismo código se carga como dos módulos distintos (afecta a los mocks).
- `chunking/splitter.py` es código sin uso.

## 9. Fases siguientes

En este repositorio, las etapas pendientes del plan (`brain/task.md`) se construyen adaptando el AI Core del equipo (`nuevamente-ai-core`) con las correcciones identificadas:

1. **IA-07, validación de fidelidad (primero):** reemplazar el crítico léxico por una verificación de cada ítem contra los chunks que cita.
2. **IA-05, selección de contexto:** cobertura por sección y por `tipo_contenido` con `get_document_chunks`, en lugar de `similarity_search(k)`.
3. **IA-06, generación** con perfiles y formatos, recibiendo la metadata pedagógica.
4. **IA-08, JSON** compatible con el contrato del backend del equipo.

## 10. Ajustes posteriores en este repositorio

Al ejecutar `scripts/test_pipeline_local.py` con una clave de Gemini nueva aparecieron dos problemas:

| Problema | Corrección |
|---|---|
| El modelo por defecto `gemini-2.5-flash` responde `404 NOT_FOUND` para claves nuevas. Sin modo estricto, el error se ocultaba y los chunks quedaban con los valores por defecto (`afirmacion`, 1, `General`). | Modelo por defecto `gemini-3.1-flash-lite`, definido en un solo lugar (`common/credentials.py`) y configurable con `GEMINI_MODEL`. Cada uso de valores por defecto registra una advertencia en el log. |
| `insert_chunks` consideraba indexado un documento comparando solo ids y textos: una clasificación corregida no reemplazaba a la anterior. | Se compara también la metadata. Si los textos no cambiaron, se actualiza solo la metadata, sin recalcular embeddings. |

Además:
- Los scripts cargan `.env` (`python-dotenv`) y usan los certificados del sistema (`truststore`), necesarios en redes que inspeccionan TLS.
- Dependencias agregadas con `uv`: `pymupdf4llm`, `truststore`, y `pytest` y `pytest-timeout` como dependencias de desarrollo. `requirements.txt` se regeneró en UTF-8 con `uv export`.
- 15 pruebas en `tests/test_dataia.py`, que pasan con Python 3.14.
