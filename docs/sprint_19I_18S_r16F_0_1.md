# Sprint 19I.18S-r16F.0.1 — Ruff import-order hotfix

## Causa

El gate focalizado de r16F pasó pruebas y mypy, pero Ruff reportó `I001`
en `public_explanation_integrity_19s_r16f.py`.

## Corrección

Se reorganiza exclusivamente el bloque de imports. No se modifica lógica,
runtime, trazabilidad, evidencia, aplicabilidad normativa, revisión humana ni
contrato de explicación.

## Criterios de aceptación

- 6 tests r16F PASS;
- Ruff limpio;
- mypy limpio;
- `git diff --check` limpio.
