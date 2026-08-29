# Sprint 19I.18J.12.1-r1 — hotfix de calidad estática

Corrige exclusivamente los hallazgos detectados por Ruff y mypy en J.12.1:

- elimina la asignación no utilizada `report`;
- ordena imports de pruebas;
- elimina `json` no utilizado en pruebas;
- introduce validación tipada `_required_string()` antes de construir `Path`
  y `TargetSource`.

No cambia el comportamiento funcional, los targets autorizados, el staging,
la política fail-closed ni los bloqueos de publicación.
