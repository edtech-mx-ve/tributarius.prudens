# Sprint 19I.18S-r10.1 — corrección mypy

Hotfix mínimo: elimina un `type: ignore[import-untyped]` innecesario en la
importación de FAISS. No cambia la lógica de reparación ni validación del
candidato público.

## Criterio de aceptación
- pruebas r10 pasan;
- Ruff limpio;
- mypy limpio en los dos módulos fuente;
- `git diff --check` limpio.
