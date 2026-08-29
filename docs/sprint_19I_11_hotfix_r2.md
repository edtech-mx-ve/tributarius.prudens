# Sprint 19I.11 hotfix r2

Corrección de compatibilidad con Ruff UP035:

- `Mapping` se importa desde `collections.abc`;
- `Any` permanece en `typing`.

No hay cambios funcionales ni de política temporal.

## Implementación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_temporal_evidence_19i11
```
