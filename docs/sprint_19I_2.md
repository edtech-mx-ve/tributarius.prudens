# Sprint 19I.2 — Puente RAG → aplicabilidad normativa

## Objetivo

Conectar evidencia normativa recuperada por RAG con el motor determinista de
aplicabilidad sin convertir recuperación semántica en autoridad jurídica.

## Política fail-closed

Un hit solo se promueve a `NormativeCandidate` cuando:

1. `source_type == normativa`;
2. tiene `version_label`;
3. contiene al menos un límite explícito `effective_from` o `effective_to`;
4. no presenta contradicción explícita entre artículo etiquetado y artículo
   encontrado al inicio del texto.

No se infiere vigencia desde `last_reform_date` ni `publication_date`.
PRODECON y UNAM nunca se promueven como normativa.

## Integración

El orquestador recupera primero RAG, construye candidatos normativos seguros,
los combina con candidatos explícitos de la solicitud y ejecuta el motor
normativo existente. Los candidatos usados quedan incorporados al resultado
para trazabilidad.

## Limitación conocida

El corpus real actual puede carecer de `effective_from/effective_to` por unidad.
En ese caso el puente se abstiene y `applicable_normative_refs` permanece vacío.
Eso es comportamiento seguro, no una autorización para inferir vigencia.

La inconsistencia observada `Artículo 1o` / texto `Artículo 2-C` se rechaza si
ambas identificaciones son explícitas en el hit. La corrección del corpus debe
hacerse en ingestión/chunking, no ocultarse en este puente.


## Hotfix r1

Se corrigió un escape doble en `_ARTICLE_RE`. La versión inicial compilaba
secuencias literales `\\b` y `\\s` en lugar de límites de palabra y espacios
regulares, por lo que la validación de consistencia artículo-etiqueta no se
ejecutaba realmente. Se añadió una prueba directa de regresión.


## Hotfix r2

La sustitución r1 no modificó el literal real del patrón en el archivo generado.
r2 reescribe directamente el bloque `_ARTICLE_RE` y deja el patrón Python como
`r"\bart(?:í|i)culo\s+(...)"`, es decir, con `\b` y `\s` interpretados por
`re` como límite de palabra y espacio, no como barras literales. Se añadió una
prueba adicional con `Artículo 2-C`.
