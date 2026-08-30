# Sprint 19I.18S-r16F.0.2 — Ruff import-order deterministic hotfix

## Causa

r16F.0.1 no resolvió I001 porque el bloque seguía compuesto por imports
`from ... import ...` y no produjo un cambio material en el orden detectado
por Ruff.

## Corrección

Se usan imports estándar directos y explícitos:

- `import collections.abc`
- `import copy`
- `import typing`

El código referencia sus símbolos mediante namespace. Esto elimina la
ambigüedad de ordenación de isort/Ruff sin suprimir I001 y sin cambiar
comportamiento.

## Invariantes

No cambia la política de integridad, estados, evidencia, aplicabilidad
normativa, revisión humana, runtime, RAG, cálculo ni explicación.

## Criterios de aceptación

- 6 tests r16F PASS;
- Ruff limpio;
- mypy limpio;
- `git diff --check` limpio.
