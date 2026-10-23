# ADR-001: Cinco formatos de salida

**Fecha:** 2026-10-22
**Estado:** Aceptada
**Enmienda:** Constitución, §6 "Formatos MVP"

## Contexto

La constitución definía tres formatos MVP: Flashcards, Quiz Interactivo y Resumen Ejecutivo. El código implementa cinco: además, Mapa Mental y Guía Paso a Paso. Se evaluó reducirlos a tres, con la hipótesis de que el mapa mental consume muchos tokens.

Medición con el contador de uso de LangChain (tokens reales informados por Gemini; generación + crítico, perfil Junior):

| Formato | JWT en OCI: entrada / salida | Salud Pública: entrada / salida |
|---|---|---|
| Quiz Interactivo | 13.014 / 2.618 | 28.053 / 1.435 |
| Flashcards | 11.523 / 1.258 | 27.766 / 1.118 |
| Guía Paso a Paso | 11.425 / 1.082 | 27.501 / 898 |
| Resumen Ejecutivo | 10.962 / 593 | 27.145 / 598 |
| Mapa Mental | 10.805 / 543 | 27.036 / 485 |

- La hipótesis no se confirma: el mapa mental es el formato con **menor** salida.
- Entre el 90 % y el 98 % de los tokens son de **entrada**: los fragmentos del documento, enviados al generador y al crítico. El formato apenas influye en el consumo; la palanca es la selección de contexto (IA-05).
- Flashcards, Quiz y Resumen ya los ofrecen otras implementaciones del proyecto. Mapa Mental y Guía Paso a Paso diferencian el producto.

## Decisión

Se mantienen los **cinco formatos** con los **tres perfiles** (Junior, Senior, Ejecutivo).

## Condiciones

La diferenciación exige que los dos formatos adicionales tengan la misma calidad que los demás. Hoy no la tienen:

- **Mapa Mental:** el árbol sale con un solo nivel (4 nodos en Salud Pública) mientras el detalle queda solo en el código Mermaid (44 líneas), y ambos no coinciden. El esquema recursivo no se aprovecha con la salida estructurada. **A resolver en IA-06:** esquema de dos o tres niveles sin recursión, con el Mermaid generado desde el árbol en el código.
- **Guía Paso a Paso:** solo es pertinente en documentos con procedimientos. **A resolver en IA-06:** verificar la proporción de chunks con `tipo_contenido` `procedimiento` o `codigo` e informar cuando el documento no sea adecuado para el formato.

## Consecuencias

- Hay más combinaciones que validar: 5 formatos × 3 perfiles × 4 dominios.
- El frontend debe representar el árbol del mapa mental (o su Mermaid) y los pasos de la guía.
