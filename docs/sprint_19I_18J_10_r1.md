# Sprint 19I.18J.10 r1 — corrección Ruff

Corrección estrictamente de estilo/importación:
`Iterable` se importa desde `collections.abc`.

No cambia la lógica ni el resultado fail-closed de J.10.

El resultado real previo es válido como diagnóstico:
- 12/14 normativos con procedencia exacta;
- LFDC y Reglamento LIVA difieren binariamente del corpus local;
- publicación, GitHub Release y Render siguen bloqueados.

No sustituir ni sobrescribir PDFs para forzar coincidencias.
