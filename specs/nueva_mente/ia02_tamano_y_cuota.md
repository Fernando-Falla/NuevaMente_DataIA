# Spec IA-02b: Tamaño de documentos y cuota del proveedor

## Contexto

Medición de los documentos de `Documentacion/` (tokens ≈ palabras × 1,3; chunks de unos 650 tokens):

| Documento | Páginas | ~Tokens | ~Chunks |
|---|---|---|---|
| JWT en OCI | 8 | 4.158 | 6 |
| VCN y subredes | 22 | 7.572 | 11 |
| TutorialPython | 155 | 66.613 | 102 |
| Oracle Certified Associate Java SE 7 (exámenes) | 3.421 | 364.149 | 560 |

Consumo actual para un documento de 364k tokens:

- **Metadata del documento:** una llamada con el texto completo (el corte está en 4 millones de caracteres), unos 364k tokens.
- **Clasificación de chunks:** unas 38 llamadas seguidas, unos 364k tokens en total.
- **Embeddings:** unos 364k tokens.

La cuota gratuita de Gemini limita peticiones y tokens **por minuto**. Una llamada que supera el límite de tokens por minuto, o una ráfaga de llamadas, produce `429 RESOURCE_EXHAUSTED`. No hay límite de entrada ni control de ritmo, y los reintentos esperan como máximo 5 s, mientras que la cuota se recupera por minuto. La extracción con `pymupdf4llm` también es lenta en documentos extensos: unos 0,4 s por página.

## Decisiones

- Un documento que excede los límites se **rechaza antes de llamar al LLM**, con un error que indica el tamaño medido, el límite y la sugerencia de dividirlo.
- Los límites por minuto se fijan de forma conservadora para la **cuenta gratuita** y se configuran por variables de entorno.

## Requisitos

- **R1. Límites de entrada, en este orden para no gastar tiempo ni cuota:**
  1. Tamaño del archivo > `DATAIA_MAX_FILE_MB` (25) → `ARCHIVO_DEMASIADO_GRANDE`, sin abrirlo.
  2. Páginas de un PDF > `DATAIA_MAX_PAGES` (300) → `DOCUMENTO_DEMASIADO_EXTENSO`, antes de extraer.
  3. Tokens estimados > `DATAIA_MAX_DOCUMENT_TOKENS` (150.000) → `DOCUMENTO_DEMASIADO_EXTENSO`, después de extraer y antes de cualquier llamada al LLM.
- **R2. Metadata del documento con un resumen acotado.** El prompt incluye la lista de títulos y extractos del inicio de cada sección, hasta `DATAIA_DOC_METADATA_MAX_TOKENS` (8.000). Nunca el texto completo.
- **R3. Control de ritmo.** Antes de cada llamada se respetan las peticiones y los tokens por minuto, en una ventana deslizante de 60 s:
  - generación: `IA_PROVIDER_RPM` (10) e `IA_PROVIDER_TPM` (200.000);
  - embeddings: `IA_EMBEDDING_RPM` (100, donde cada chunk cuenta como una petición) e `IA_EMBEDDING_TPM` (20.000).

  El límite de 20.000 deja margen sobre los 30.000 tokens por minuto de la cuenta gratuita. La validación mostró que la estimación local se queda hasta un 25 % corta en documentos con mucho código: con 30.000 hubo 6 respuestas 429 en "TutorialPython", y con 20.000, ninguna.

  Los valores por defecto son una estimación prudente para la cuenta gratuita; se ajustan según los límites que muestre Google AI Studio para la clave.
- **R4. Espera ante un 429.** Se espera el tiempo que indica el proveedor (`retryDelay`) o 60 s si no lo indica, y se reintenta hasta `IA_PROVIDER_QUOTA_RETRIES` veces (2). Los demás errores conservan el comportamiento actual.
- **R5. Embeddings por lotes propios,** de hasta 20 chunks (`DATAIA_EMBEDDING_BATCH_SIZE`) y no más de un tercio de `IA_EMBEDDING_TPM`, cada lote sujeto al control de ritmo.
- **R6. Estimación previa.** El resultado de la ingestión informa los tokens estimados del documento.

## Criterios de aceptación

- **CA1.** El PDF de 3.421 páginas se rechaza en menos de 2 s, sin llamadas al LLM y con un mensaje que incluye páginas y límite.
- **CA2.** Un texto de más de 150.000 tokens se rechaza sin llamadas al LLM.
- **CA3.** El prompt de metadata de "TutorialPython.pdf" (66k tokens) no supera los 8.000 tokens estimados y contiene sus títulos.
- **CA4.** Pruebas sin red del control de ritmo (espera cuando se agota la ventana) y de la espera ante un 429.
- **CA5.** El pipeline real procesa "TutorialPython.pdf" sin errores 429.
