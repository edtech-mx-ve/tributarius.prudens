# Sprint 9 — Motor de reglas

## Objetivo

Ejecutar inferencia simbólica determinista, versionada, trazable y desacoplada de Llama.

## Flujo

`hechos → normas aplicables → reglas → condiciones → conclusiones → trazas`

Las reglas con `normative_refs` solo se activan si esas referencias fueron previamente
validadas como aplicables por el motor normativo.

## Operadores

`eq`, `ne`, `in`, `not_in`, `gt`, `gte`, `lt`, `lte`, `exists`.

## Seguridad y robustez

No se usa `eval`, `exec` ni deserialización insegura. El cargador acepta JSON validado,
limita archivos a 5 MB, conjuntos a 5000 reglas, 50 condiciones por regla y 500 hechos
por evaluación. Cada condición genera una traza reproducible.

## Limitaciones

Las condiciones de una regla se combinan por AND. No se implementa todavía
encadenamiento de conclusiones, resolución semántica de conflictos ni persistencia de
hechos derivados. Estas extensiones deben justificarse con casos fiscales concretos.
