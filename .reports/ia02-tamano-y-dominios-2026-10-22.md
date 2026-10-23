# Reporte de validación — IA-02b (tamaño y cuota) e IA-02c (dominios)

**Fecha:** 2026-10-22
**Specs:** `specs/nueva_mente/ia02_tamano_y_cuota.md`, `specs/nueva_mente/ia02_dominios.md`
**Modelo:** `gemini-3.5-flash-lite` y `models/gemini-embedding-001`, cuenta gratuita, `IA_STRICT_PROVIDERS=1`
**Pruebas automáticas:** 62 pasan sin red (`uv run pytest`)

## IA-02b: tamaño y cuota

| Criterio | Resultado |
|---|---|
| CA1. PDF de 3.421 páginas | ✅ `DOCUMENTO_DEMASIADO_EXTENSO` en 0,05 s, sin llamadas al LLM: "El documento tiene 3421 páginas y el límite es 300" |
| CA2. Texto de más de 150.000 tokens | ✅ Rechazado sin llamadas al LLM (prueba automática) |
| CA3. Resumen para metadata de "TutorialPython.pdf" | ✅ Documento ~81.102 tokens → resumen ~7.981 tokens, con sus 236 títulos |
| CA4. Control de ritmo y espera ante 429 | ✅ Pruebas automáticas con reloj simulado |
| CA5. "TutorialPython.pdf" completo sin 429 | ✅ 15 lotes de embeddings, 12 esperas preventivas, 0 respuestas 429, 260 s |

Antes de las correcciones, ese documento enviaba unos 81k tokens en una sola llamada de metadata y fallaba en los embeddings con `429 RESOURCE_EXHAUSTED`.

### Ajuste de los límites de embeddings

| Configuración | Respuestas 429 | Resultado |
|---|---|---|
| Lotes de 50 chunks, una petición por lote | 15 | Fallo tras 178 s |
| Lotes por tokens, cada chunk como petición, `IA_EMBEDDING_TPM=30000` | 6 (absorbidas con 3 esperas de 60 s) | Éxito en 281 s |
| Ídem, `IA_EMBEDDING_TPM=20000` (valor por defecto) | 0 | Éxito en 260 s |

El cliente de LangChain divide cada lote en varias peticiones HTTP, y la estimación local de tokens se queda hasta un 25 % corta con texto que tiene mucho código.

## IA-02c: dominios

| Criterio | Resultado |
|---|---|
| CA1. Léxico de respaldo (sin red) | ✅ Salud, Fintech, Marketing digital y TI con su dominio; receta rechazada |
| CA2. Clasificación con Gemini real | ✅ Ver tabla |
| CA3. Pipeline completo por dominio | ✅ Ver tabla |
| CA4. Sin sesgo de TI en perfiles, consulta y contingencia | ✅ Revisión del código |

### CA2: clasificación

| Documento | Resultado | Dominio | Justificación del LLM (extracto) |
|---|---|---|---|
| VCN y subredes.pdf | Aprobado | TI | "guía oficial de configuración de infraestructura de red y bases de datos en la nube" |
| fintech_conciliacion_pagos.md (ficticio) | Aprobado | Fintech | "describe procesos de pago, comisiones, conciliación y normativas financieras" |
| salud_protocolo_hipertension.md (ficticio) | Aprobado | Salud | "protocolo clínico y normativo para el manejo de la hipertensión arterial" |
| marketing_campanas_ppc.md (ficticio) | Aprobado | Marketing digital | "métricas, estructuras y optimizaciones avanzadas de SEM" |
| no_tecnico_receta.md | `DOMINIO_NO_SOPORTADO` | Otro | "receta culinaria de divulgación general" |

Con el validador anterior, los cuatro documentos técnicos se habrían rechazado.

### CA3: pipeline completo

| Documento | Perfil | Formato | Nicho | Score | Ítems |
|---|---|---|---|---|---|
| fintech_conciliacion_pagos.md | Senior | Quiz Interactivo | Fintech | 1,0 | 3 |
| salud_protocolo_hipertension.md | Junior | Flashcards | Salud | 1,0 | 6 |
| marketing_campanas_ppc.md | Ejecutivo | Resumen Ejecutivo | Marketing digital | 1,0 | 3 |
| VCN y subredes.pdf | Junior | Mapa Mental | TI | 1,0 | 1 |

En Salud, la introducción incluye el aviso de material educativo y las cifras se reproducen exactamente (130–139 / 80–89 mmHg, 5 minutos de reposo).

### Observación: ortografía

En una ejecución, el contenido de Salud se generó sin tildes ni signos de apertura. Se agregó al generador una instrucción explícita de ortografía; la repetición tuvo 63 tildes y signos. En el código Mermaid el modelo todavía omite algunas tildes.

## Limitaciones

- Los documentos de Fintech, Salud y Marketing digital son **ficticios**, escritos para estas pruebas. Hay que repetir la validación con documentos reales de cada dominio.
- Los límites por minuto son estimaciones para la cuenta gratuita; se ajustan con variables de entorno según Google AI Studio.

## Pendiente (IA-06)

En los mapas mentales, el árbol (`arbol`) y el código Mermaid que escribe el modelo no coinciden: el árbol tiene solo las ramas principales. Conviene generar el Mermaid desde el árbol.

## Conclusión

- [x] IA-02b validada
- [x] IA-02c validada con documentos ficticios; pendiente con documentos reales
