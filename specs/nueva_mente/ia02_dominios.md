# Spec IA-02c: Dominios de documentos (TI, Fintech, Salud, Marketing digital)

## Contexto

NuevaMente debe procesar documentos técnicos de cuatro dominios: **TI, Fintech, Salud y Marketing digital**. El validador de pertinencia actual busca 24 palabras de TI (cloud, JWT, VCN, OCI…) como subcadenas. Probado con textos breves de cada dominio:

| Texto | Resultado |
|---|---|
| Salud (protocolo de hipertensión) | Rechaza ("api" se encontró dentro de "terapia") |
| Fintech (conciliación de pagos) | Rechaza |
| Marketing digital (campaña de pago por clic) | Rechaza |
| TI (Kubernetes) | Rechaza |
| Receta de cocina | Rechaza (correcto) |

La generación también está sesgada hacia TI:

- perfil Senior: "arquitecto de software y consultor cloud";
- perfil Junior: "analogías de infraestructura, redes o código";
- perfil Ejecutivo: "costos de infraestructura";
- consulta de recuperación: "arquitectura";
- contenido de contingencia sobre arquitectura y redes.

La lista de nichos (Fintech, Salud, E-commerce, General) no incluye TI ni Marketing digital.

## Conceptos

- **Dominio:** de qué trata el documento. Lo detecta el sistema.
- **Nicho:** el sector al que se adaptan ejemplos y analogías. Lo elige el usuario.

## Requisitos

- **R1. Detección del dominio en la llamada de metadata existente,** sin llamadas adicionales. `DocumentPedagogicalMetadata` agrega:
  - `dominio`: `TI`, `Fintech`, `Salud`, `Marketing digital` u `Otro`;
  - `es_documento_tecnico`: `bool`;
  - `justificacion_dominio`: `str`.
- **R2. Rechazo por dominio.** Si `dominio == "Otro"` o el documento no es técnico → `DOMINIO_NO_SOPORTADO`, con la justificación en el mensaje.
- **R3. Respaldo determinista.** Si el LLM no está disponible (modo no estricto), un léxico por dominio decide. Usa coincidencias de palabra completa, sin distinguir acentos ni mayúsculas, y exige al menos 3 términos distintos de un mismo dominio. El validador anterior se reemplaza.
- **R4. Nichos:** `TI`, `Fintech`, `Salud`, `Marketing digital`, `General`. Se elimina `E-commerce`.
- **R5. Generación neutral respecto del dominio:**
  - los perfiles describen el rol sin atarlo a TI;
  - el analizador agrega pautas del dominio del documento;
  - la consulta de recuperación y el contenido de contingencia no mencionan conceptos de TI.
- **R6. Pautas por dominio:**
  - **TI:** comandos, código, versiones y nombres de configuración exactos.
  - **Fintech:** cifras, tasas, plazos y normas exactos; sin recomendaciones de inversión.
  - **Salud:** dosis, unidades y umbrales exactos; sin consejo médico personal; se aclara que es material educativo.
  - **Marketing digital:** métricas y fórmulas tal como las define la fuente (CTR, CPA, ROAS…); sin prometer resultados.

## Criterios de aceptación

- **CA1.** Con el léxico de respaldo, los cinco textos de prueba se clasifican así: los cuatro técnicos se aceptan con su dominio correcto y la receta se rechaza. Prueba sin red.
- **CA2.** Con Gemini real, documentos de los cuatro dominios se aceptan con el dominio correcto y un documento no técnico se rechaza con `DOMINIO_NO_SOPORTADO`.
- **CA3.** El pipeline completo genera contenido aprobado por el crítico para un documento de cada dominio.
- **CA4.** Ningún prompt de perfil, consulta ni contenido de contingencia menciona conceptos exclusivos de TI.

## Fuera de alcance

- Formatos DOCX o HTML: se siguen aceptando PDF, Markdown y TXT.
- Dominios adicionales: el modelo admite agregarlos con su léxico y sus pautas.
