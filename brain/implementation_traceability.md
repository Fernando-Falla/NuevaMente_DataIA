# Registro de Implementacion y Trazabilidad

**Proyecto:** NuevaMente DataIA Pipeline  
**Fecha de consolidacion:** 2026-09-23  
**Alcance:** Correcciones definitivas de IA-02, IA-03, IA-04 y del script de prueba local.

## Estado definitivo

El flujo local implementado es:

```text
Documento PDF/TXT/MD
  -> IA-02: ingestion, validacion y normalizacion
  -> IA-03: chunking jerarquico y metadatos
  -> IA-04: Gemini embeddings y ChromaDB persistente
```

La prueba local se ejecuta desde PowerShell con `scripts/test_pipeline_local.py`.

## Cambios aplicados

### Dependencias

En `pyproject.toml` quedaron declaradas las integraciones actuales:

- `langchain-text-splitters`: proporciona `RecursiveCharacterTextSplitter`.
- `langchain-chroma`: proporciona la integracion de Chroma sin depender de `langchain-community`.
- `langchain-google-genai`: cliente de embeddings de Gemini.
- `pymupdf`: extraccion de texto PDF mediante `import pymupdf`.

El lockfile se valida con `uv lock --check`.

### Imports actualizados

- `src/dataia/chunking/splitter.py` usa `langchain_text_splitters`.
- `src/dataia/vectorstore/client.py` usa `langchain_chroma.Chroma`.
- `src/dataia/ingestion/service.py` usa `pymupdf` en lugar de la API deprecada `fitz`.

### Modelo de embeddings

El modelo anterior `models/text-embedding-004` producia un error 404 con la API disponible.

El modelo definitivo es:

```text
models/gemini-embedding-001
```

Puede sobrescribirse sin editar codigo mediante:

```powershell
$env:GOOGLE_EMBEDDING_MODEL = "models/gemini-embedding-001"
```

### API key

La API key **no se almacena en el repositorio ni en `.env.example`**.

El script acepta estas variables de entorno:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

Si solo existe `GEMINI_API_KEY`, el script la normaliza internamente al nombre esperado por el cliente.

Definir la clave en la misma terminal donde se ejecuta Python:

```powershell
$env:GOOGLE_API_KEY = "TU_API_KEY_REAL"
```

Verificar que existe sin imprimir su contenido:

```powershell
[bool]$env:GOOGLE_API_KEY
```

Debe devolver `True`.

`.env.example` solo contiene una plantilla:

```env
GOOGLE_API_KEY=your_google_api_key_here
```

Un archivo `.env` real queda excluido por `.gitignore`, pero la forma recomendada para estas pruebas es la variable de sesión de PowerShell.

> La clave que anteriormente estuvo escrita en `.env.example` debe considerarse expuesta, revocarse y regenerarse.

## Ejecucion

### Un documento

Desde la raiz del repositorio:

```powershell
$env:GOOGLE_API_KEY = "TU_API_KEY_REAL"
.\.venv\Scripts\python.exe scripts\test_pipeline_local.py "ruta\al\documento.pdf"
```

El script acepta PDF, TXT y MD, siempre que el contenido pase la validacion tecnica de IA-02.

### Varios documentos

```powershell
Get-ChildItem ".\documentos" -File |
    Where-Object { $_.Extension -in ".pdf", ".txt", ".md" } |
    ForEach-Object {
        Write-Host "`nProcesando $($_.FullName)"
        .\.venv\Scripts\python.exe scripts\test_pipeline_local.py $_.FullName
    }
```

La variable solo dura en la sesion actual. Para eliminarla:

```powershell
Remove-Item Env:GOOGLE_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
```

## Persistencia ChromaDB

La persistencia local se guarda en:

```text
.chromadb_data/
```

La coleccion configurada es `nuevamente_docs`.

Al consolidar estos cambios, la coleccion local existente estaba vacia, por lo que no fue necesario migrar vectores del modelo anterior.

## Diagnostico de errores resueltos

| Sintoma | Causa | Resolucion |
| --- | --- | --- |
| `python` no encontrado | Alias de Microsoft Store y ausencia de Python global en PATH | Usar `.venv\\Scripts\\python.exe` |
| `No module named langchain.text_splitter` | API separada en versiones actuales de LangChain | Instalar `langchain-text-splitters` y actualizar import |
| `No module named langchain_community` | Dependencia no declarada | Sustituir por `langchain-chroma` |
| Aviso de `fitz` deprecado | Import antiguo de PyMuPDF | Usar `import pymupdf` |
| `GOOGLE_API_KEY` ausente | La variable no existia en la sesion que ejecutaba Python | Definirla en la misma terminal |
| `text-embedding-004` 404 | Modelo no disponible para `embedContent` en la API activa | Usar `models/gemini-embedding-001` |

## Validaciones realizadas

- Compilacion de `scripts/test_pipeline_local.py` con `py_compile`.
- Compilacion de `src/dataia/vectorstore/client.py`.
- Imports de ingestion, chunking y vector store correctos.
- Normalizacion comprobada de `GEMINI_API_KEY` a `GOOGLE_API_KEY`.
- `uv lock --check` correcto.
- Errores del editor: ninguno en los archivos modificados.
- La ejecucion sin argumento muestra el uso esperado del script.

## Pendientes del proyecto

Las siguientes fases no forman parte de esta correccion y permanecen pendientes:

- IA-05: Retriever/RAG.
- IA-06: Generacion LLM y perfiles pedagogicos.
- IA-07: Validacion de fidelidad.
- IA-08: Integracion y salida JSON.

## Archivos relevantes

- `pyproject.toml`
- `uv.lock`
- `scripts/test_pipeline_local.py`
- `src/dataia/ingestion/service.py`
- `src/dataia/chunking/splitter.py`
- `src/dataia/vectorstore/client.py`
- `.env.example`
- `.gitignore`
