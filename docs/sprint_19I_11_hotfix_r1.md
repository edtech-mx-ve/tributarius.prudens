# Sprint 19I.11 hotfix r1

Corrección estática del auditor temporal:

- elimina import no usado reportado por Ruff;
- añade `_summary_int()` para estrechar de forma segura los valores `object`
  del resumen producido por la auditoría 19I.3;
- evita reutilización del nombre `item` entre tipos distintos al serializar CSV.

No cambia la política temporal, no infiere vigencias y no modifica corpus,
embeddings ni FAISS.

## Implementación local

```powershell
pytest tests/test_normative_temporal_evidence_19i11.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_temporal_evidence_19i11
```
