# Sprint 19I.18S-r16C — Trace Integrity

## Evidencia que motiva el incremento

El smoke local r16B.1 conserva correctamente los gates r15:

- `requires_human_review=True`;
- `applicable_normative_refs=0`;
- `primary_intent=calculate_iva`;
- `query_fiscal_year=2026`;
- backend `legal_hybrid_lexical_cpu_19s_r14`.

Sin embargo, el evento `normative` continúa con
`requires_human_review=False` y el resumen sólo informa cero referencias.

## Diseño r16C

Se introduce una función pura de reconciliación para respuestas serializadas.
La revisión se propaga al stage `normative` únicamente cuando concurren:

1. revisión global ya requerida;
2. evidencia normativa recuperada;
3. cero referencias normativas aplicables.

No se cambia la decisión jurídica, no se promueve evidencia y no se altera el
orquestador. La función es deliberadamente no mutante.

## Integración

r16C establece y prueba la semántica. r16C.1 conectará la reconciliación en la
frontera JSON junto con la normalización Unicode, una vez que este gate pase.

## Criterios de aceptación

- 6 tests nuevos;
- gate acumulado r16 verde;
- Ruff/mypy/diff-check verdes;
- runtime r10, lexical_cpu, temporal policy y Render intactos.
