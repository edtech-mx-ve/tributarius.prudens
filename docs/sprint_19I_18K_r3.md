# Sprint 19I.18K-r3 — coherencia del manifest normative-only

El rebuild 19I.8 rechazó correctamente el staging con:

`promoted_chunks=2981; esperado=2962`

Diagnóstico: el canonical normative-only sí fue filtrado a 2962 parents, pero
el manifest derivado conservó el campo exacto `promoted_chunks=2981`. La
expresión genérica de r2 no reconocía `promoted_chunks` porque ese nombre no
contiene `count` ni `total`.

r3 corrige exclusivamente la transformación del manifest:

- reconoce explícitamente `promoted_chunks` y otros nombres de cardinalidad;
- actualiza `promoted_chunks` al cardinality real normative-only;
- añade prueba de regresión que exige 2962 y preserva números no relacionados;
- mantiene fail-closed y no toca el runtime interno.

Antes de reintentar debe borrarse únicamente
`dist/public_safe_runtime_19i18k`, que es staging incompleto.
