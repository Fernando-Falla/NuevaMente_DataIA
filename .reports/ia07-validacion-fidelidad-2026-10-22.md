# Reporte de validación — IA-07 (agente crítico)

**Fecha:** 2026-10-22
**Spec:** `specs/nueva_mente/ia07_validacion_fidelidad.md`
**Modelo:** `gemini-3.5-flash-lite` (generación y juez), `models/gemini-embedding-001` (embeddings), `IA_STRICT_PROVIDERS=1`

## Discriminación del juez

Documento "JWT en OCI.pdf" (9 chunks). Borradores de 2 flashcards evaluados directamente con `nodo_critico`, dos ejecuciones por caso.

| Caso | Juez del equipo (`06f6afd`) | Juez por ítem (IA-07) | Criterio |
|---|---|---|---|
| CA1. Fiel al documento | 1,0 / 1,0 | 1,0 / 1,0 | ≥ 0,85 ✅ |
| CA2. Con datos inventados | 0,0 / 0,0 | 0,0 / 0,0 | < 0,75 ✅ |
| CA3. Fiel, con analogías en `pista_didactica` | 0,5 / 1,0 | 1,0 / 1,0 | ≥ 0,85 ✅ |

Retroalimentación del juez por ítem en el caso CA2 (primera ejecución):

> Ítem 1 (¿Qué partes tiene un JWT?), sin respaldo: El contenido afirma que un JWT tiene cinco partes (incluyendo sal criptográfica y un checksum CRC32), lo cual contradice la fuente que indica que consta únicamente de cabecera, carga útil y firma.
>
> Ítem 2 (¿Cuánto dura un JWT en OCI?), sin respaldo: El contenido afirma que OCI fija una expiración de 24 horas obligatoria, exige firmas SHA-1 y no admite JWKS remoto, lo cual contradice la fuente que menciona soporte para REMOTE_JWKS y no establece expiración fija obligatoria ni SHA-1.

## Pipeline completo (CA4)

`scripts/run_pipeline_real.py`, con la ingestión y la clasificación de chunks ya en caché.

| Documento | Perfil | Formato | Nicho | Score | Ítems | Auditoría | Tiempo |
|---|---|---|---|---|---|---|---|
| JWT en OCI | Junior | Flashcards | General | 1,0 | 5 | Seguro | 9,8 s |
| VCN y subredes | Senior | Quiz Interactivo | Fintech | 1,0 | 5 | Seguro | 11,4 s |
| VCN y subredes | Ejecutivo | Resumen Ejecutivo | E-commerce | 1,0 | 1 | Seguro | 8,4 s |
| Arquitectura de microservicios | Junior | Mapa Mental | Salud | 1,0 | 1 | Seguro | 5,6 s |

Con el crítico léxico original, "JWT en OCI" (Junior, Flashcards) terminaba en 422 "Contexto Insuficiente" (score 0,78).

## Corrección asociada

El auditor heurístico buscaba la clave `contenido`, pero la respuesta usa `contenido_adaptado`: todas las ejecuciones se marcaban como "no seguras" con "Estructura rota". Corregido; ahora la revisión de integridad evalúa el contenido real.

## Conclusión

- [x] IA-07 validada (CA1–CA5)
- [ ] Requiere ajustes

Pendiente para IA-05/IA-06: la metadata pedagógica del documento todavía no llega a los agentes (los `conceptos_clave` de la respuesta salen de una heurística de mayúsculas).
