# Sprint 19I.7.10 — auditoría de cambios de identidad

19I.7.9 resolvió 7 de 21 residuos y dejó 14 casos
`parser_accepts_identity_changed_requires_review`.

Este incremento determina si esos 14 casos:
- preservan la identidad detectada por el parser;
- duplican la identidad;
- fueron etiquetados con una identidad distinta;
- fueron fusionados bajo una unidad vecina;
- o carecen de contenedor candidato.

No modifica corpus, candidato, embeddings ni FAISS.

## Implementación local

```powershell
pytest tests/test_legal_identity_change_audit_19i710.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_identity_changes_19i710
```

Salidas:
- `reports/sprint19I710/legal_identity_change_audit.json`
- `reports/sprint19I710/legal_identity_change_findings.csv`
