# Sprint 19I.7.8 — control residual previo a promoción

19I.7.7 cerró las 135 fronteras numéricas legítimas y dejó `unresolved=0`.
Antes de promover el candidato todavía deben revisarse los residuos que no
pertenecían a ese conjunto:

- 9 `ambiguous_numeric_boundary_requires_review`;
- 12 `absorbed_other_boundary`;
- 4 `missing_reference_like_boundary`.

Este incremento consolida esos casos y verifica si el texto 19C permanece
contenido en alguna unidad candidata. No promueve ni modifica el corpus.

## Implementación local

```powershell
pytest tests/test_semantic_residual_audit_19i78.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_semantic_residuals_19i78
```

Salidas:
- `reports/sprint19I78/semantic_residual_audit.json`
- `reports/sprint19I78/semantic_residual_findings.csv`
