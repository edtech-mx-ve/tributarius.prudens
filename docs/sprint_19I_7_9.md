# Sprint 19I.7.9 — contraste fuente ↔ parser ↔ identidad

19I.7.8 dejó 21 casos en revisión:

- 9 `ambiguous_numeric_text_preserved_requires_review`;
- 12 `other_boundary_text_preserved_requires_review`.

Este incremento no muta el corpus. Para cada caso contrasta:

1. primera línea de la unidad 19C;
2. presencia en Markdown normalizado;
3. patrones actuales de artículo, regla, estructura y heading;
4. identidad estructural equivalente en el candidato;
5. preservación integral del texto.

La resolución automática solo considera segura:
- identidad estructural única preservada; o
- frontera rechazada por el parser actual con texto íntegramente preservado.

## Implementación local

```powershell
pytest tests/test_semantic_source_residual_audit_19i79.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_semantic_source_residuals_19i79
```

Salidas:
- `reports/sprint19I79/semantic_source_residual_audit.json`
- `reports/sprint19I79/semantic_source_residual_findings.csv`
