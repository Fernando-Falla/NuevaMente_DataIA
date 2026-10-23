# Spec IA-07: Validación de fidelidad (agente crítico)

## Contexto

El AI Core del equipo (commit `06f6afd`) reemplazó el crítico léxico por un juez LLM que devuelve un único score de 0 a 1. Medido con Gemini real sobre "JWT en OCI.pdf" (9 chunks):

| Borrador | Score (2 ejecuciones) |
|---|---|
| Fiel al documento | 1,0 / 1,0 |
| Con datos técnicos inventados | 0,0 / 0,0 |
| Fiel, con analogías didácticas en `pista_didactica` | 0,5 / 1,0 |

El juez detecta las invenciones, pero:

1. Su regla prohíbe "analogías no presentes en la fuente", mientras el perfil Junior exige analogías y el generador debe adaptar ejemplos al nicho. El resultado depende de cómo el LLM resuelva esa contradicción en cada ejecución.
2. El score es un único número elegido por el LLM: varía entre ejecuciones y no indica qué ítem falla.
3. La retroalimentación al generador es un texto general, sin ítems concretos.

## Requisitos

- **R1. Campos factuales y didácticos.** Los campos que afirman hechos técnicos (`dorso`, `pregunta`, opción correcta, `justificacion_tecnica`, `tldr`, `puntos_clave`, ramas del mapa mental, etc.) deben estar respaldados por la fuente. Los recursos didácticos (`pista_didactica`, analogías, ejemplos de nicho) pueden no figurar en la fuente, pero no pueden introducir datos técnicos falsos ni contradecirla.
- **R2. Veredicto por ítem.** El juez clasifica cada ítem como `respaldado`, `parcial` o `sin_respaldo`, con una observación que nombra la afirmación problemática.
- **R3. Score calculado en código.** `anclaje_fuente_score = (respaldados + 0,5 × parciales) / total de ítems`. Un ítem que el juez omite cuenta como `parcial`.
- **R4. Quiz.** Las opciones incorrectas son falsas a propósito: se verifican la opción correcta, `justificacion_tecnica` y `explicacion_distractores`.
- **R5. Retroalimentación accionable.** Ante un reintento, el generador recibe la lista de ítems no respaldados con su observación.
- **R6. Se conserva:** contexto vacío → score 0,0 sin llamar al LLM; fallo del proveedor → excepción en modo estricto, score 0,5 en modo no estricto; umbrales 0,85 (0,75 en Quiz) y máximo dos intentos.

## Criterios de aceptación

Validados con Gemini real sobre "JWT en OCI.pdf", dos ejecuciones por caso:

- **CA1.** Borrador fiel → score ≥ 0,85 en ambas ejecuciones.
- **CA2.** Borrador con datos inventados → score < 0,75 en ambas, y la observación nombra los ítems inventados.
- **CA3.** Borrador fiel con analogías en `pista_didactica` → score ≥ 0,85 en ambas.
- **CA4.** El pipeline completo produce contenido para las combinaciones Junior/Flashcards, Senior/Quiz, Ejecutivo/Resumen y Junior/Mapa Mental.
- **CA5.** Pruebas automáticas sin red para R2, R3, R5 y R6.

## Fuera de alcance

- Selección de contexto (IA-05) y uso de la metadata pedagógica en la generación (IA-06).
- Citas de `chunk_id` por ítem: requieren cambiar el esquema de salida del generador (IA-06/IA-08).
