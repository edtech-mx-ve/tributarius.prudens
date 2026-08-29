# Sprint 19I.12 hotfix r1

Corrección estática reportada por Ruff UP035:

- `Iterable` se importa desde `collections.abc`.

No hay cambios funcionales, de clasificación temporal ni de política fail-closed.

## Implementación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.review_priority_temporal_evidence_19i12
```
