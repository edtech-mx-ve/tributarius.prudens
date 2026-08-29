# Sprint 19I.14 hotfix r1

Corrección estática reportada por Ruff E501:

- se extrae el conteo `requires_human_verification_document_scope`
  a una variable local;
- no cambia la lógica, el registro temporal ni la política fail-closed.

## Implementación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.build_temporal_provenance_registry_19i14
```
