# Spec IA-08: Contrato JSON con Backend

## Contexto

El pipeline Data & IA procesa documentos técnicos desde la ingestión hasta la validación de fidelidad (IA-02 a IA-07). Para que el Backend (API Gateway / Core de aplicación) y posteriormente el Frontend consuman el contenido educativo generado, se requiere un **contrato de interfaz estable, fuertemente tipado y serializable en JSON estándar**.

Actualmente:
- Las etapas intermedias producen estructuras de datos ricas (`pedagogical_metadata`, `chunk_id`, evaluaciones de fidelidad del crítico, reportes de auditoría), pero la respuesta canónica previa (`AdaptacionContenidoResponse`) solo expone una parte y no incluye de forma estandarizada los metadatos de trazabilidad de fuentes ni un contrato unificado para errores de negocio (400, 413, 422).
- Backend necesita recibir respuestas predictibles tanto en éxito como en rechazos controlados (ej. documento de dominio no soportado, documento sin procedimientos para Guía Paso a Paso, o fallo en el anclaje a fuentes).

---

## Requisitos

### R1. Contrato de Entrada (Request DTO)
El payload de entrada para solicitud de adaptación debe ser validado con Pydantic V2 (`AdaptacionContenidoRequest` / `AdaptacionRequestDTO`):
- `documento_titulo`: string (3-150 caracteres).
- Entrada de documento: soporta `ruta_archivo` (archivo local o temporal subido por Backend) o `document_id` (documento previamente ingestrado e indexado en ChromaDB).
- `perfil_destinatario`: Enum `Junior` | `Senior` | `Ejecutivo`.
- `formato_salida`: Enum `Flashcards` | `Quiz Interactivo` | `Mapa Mental` | `Guia Paso a Paso` | `Resumen Ejecutivo`.
- `nicho_sector`: Enum `TI` | `Fintech` | `Salud` | `Marketing digital` | `General` (default `General`).
- `nivel_detalle`: Enum `Didactico` | `Tecnico Intermedio` | `Exhaustivo` (default `Didactico`).
- Sanitización de entrada: detección estricta de XSS y patrones comunes de Prompt Injection previa ejecución.

### R2. Contrato de Salida en Éxito (Success Response DTO)
Cuando el pipeline finaliza y el Agente Crítico aprueba la fidelidad, la respuesta (`AdaptacionResponseDTO`) debe contener:
```json
{
  "status": "exito",
  "documento": {
    "document_id": "doc-a1b2c3d4",
    "titulo": "Arquitectura de Microservicios",
    "dominio": "TI"
  },
  "metadatos": {
    "perfil_aplicado": "Junior",
    "formato_generado": "Flashcards",
    "nicho_contexto": "General",
    "tiempo_estimado_estudio_minutos": 15,
    "conceptos_clave": ["Microservicios", "API Gateway", "Contenedores"],
    "resumen_ejecutivo": "Síntesis pedagógica del documento..."
  },
  "contenido_adaptado": {
    "titulo": "Fundamentos de Microservicios para Junior",
    "introduccion_contextualizada": "Introducción amigable con analogías...",
    "items": [ /* Estructura específica y validada del formato solicitado */ ]
  },
  "trazabilidad": {
    "chunks_utilizados": [
      {
        "chunk_id": "doc-a1b2c3d4-chk-0001",
        "seccion": "1. Introducción",
        "pagina_inicio": 1,
        "pagina_fin": 2,
        "tipo_contenido": "definicion"
      }
    ],
    "total_chunks_documento": 12,
    "total_chunks_contexto": 4
  },
  "validacion": {
    "anclaje_fuente_score": 0.95,
    "aprobado": true,
    "reintentos_realizados": 0,
    "auditoria_seguridad": {
      "es_seguro": true,
      "vulnerabilidades": []
    }
  }
}
```

### R3. Esquemas de Contenido por Formato (`contenido_adaptado.items`)
Cada formato cuenta con su estructura canónica tipada:
1. **Flashcards:** Lista de objetos `{ frente, dorso, pista_didactica, categoria_dificultad }` (4 a 8 tarjetas).
2. **Quiz Interactivo:** Lista de objetos `{ pregunta, opciones (exactamente 4), indice_correcto (0-3), justificacion_tecnica, pista_didactica, explicacion_distractores }` (3 a 5 preguntas).
3. **Mapa Mental:** Objeto `{ nodo_central, descripcion_general, arbol: [NodoMapaMental], codigo_mermaid }`. El árbol y el Mermaid son generados deterministamente de forma idéntica (IA-06 R7).
4. **Guía Paso a Paso:** Objeto `{ prerrequisitos: [str], pasos: [{ numero_paso, titulo_paso, instrucciones, bloque_codigo, resultado_esperado }], resumen_cierre }`.
5. **Resumen Ejecutivo:** Objeto `{ tldr, puntos_clave: [str], impacto_negocio, recomendaciones: [str] }`.

### R4. Contrato de Error Tipado (Error Response DTO)
Ante cualquier rechazo controlado del pipeline (sin lanzar excepciones no capturadas al cliente HTTP), el servicio retornará un objeto estructurado:
```json
{
  "status": "error",
  "codigo_error": "FORMATO_NO_ADECUADO",
  "http_status": 422,
  "mensaje": "El documento no contiene suficientes procedimientos o código para estructurar una Guía Paso a Paso.",
  "detalle": {
    "chunks_procedimiento": 1,
    "porcentaje_procedimiento": 4.7
  },
  "sugerencia": "Te recomendamos generar un Mapa Mental, Resumen Ejecutivo o Flashcards para este documento conceptual."
}
```

Catálogo de errores canónicos:
| Código de Error | HTTP Status | Causa |
|---|---|---|
| `DOMINIO_NO_SOPORTADO` | 400 | El documento no pertenece a TI, Fintech, Salud o Marketing digital |
| `ARCHIVO_INVALIDO` | 400 | Extensión no permitida o archivo corrupto |
| `ARCHIVO_DEMASIADO_GRANDE` | 413 | Tamaño > 25 MB |
| `DOCUMENTO_DEMASIADO_EXTENSO` | 413 | > 300 páginas o > 150.000 tokens estimados |
| `FORMATO_NO_ADECUADO` | 422 | Guía Paso a Paso solicitada en documento conceptual (< 2 chunks o < 15 % de procedimiento/código) |
| `FIDELIDAD_INSUFICIENTE` | 422 | El Agente Crítico no aprobó el contenido tras reintentos (score < umbral) |
| `ERROR_PROVEEDOR_LLM` | 503 | Falla de cuota (429) no recuperable o indisponibilidad del proveedor |
| `ERROR_INTERNO` | 500 | Error no contemplado durante la ejecución |

### R5. Serialización Limpia y Exportación JSON Schema
- Serialización UTF-8 directa (sin escapes innecesarios `\uXXXX` en caracteres acentuados o símbolos matemáticos).
- Generación de scripts y esquemas JSON exportables (`.json`) para facilitar la generación de clientes en Spring Boot / TypeScript.

---

## Criterios de Aceptación

- **CA1. Serialización y Validación de Contratos:** Pruebas unitarias sin red que validen que payloads de éxito para los 5 formatos serializan y deserializan exactamente bajo los modelos Pydantic v2.
- **CA2. Trazabilidad Completa:** La respuesta en éxito incluye `document_id`, `chunks_utilizados` con metadata de sección y página, y el reporte del crítico y auditor.
- **CA3. Errores Tipados Controlados:** Pruebas que verifiquen que `DOMINIO_NO_SOPORTADO` y `FORMATO_NO_ADECUADO` devuelven el esquema de error con su código, HTTP status sugerido y sugerencia didáctica, sin producir excepciones no manejadas.
- **CA4. Exportación de Esquemas:** Existencia de una utilidad para generar los esquemas JSON (`schema_request.json`, `schema_response_success.json`, `schema_response_error.json`).

