# Sprint 19I.7.5 — desambiguación de fronteras duplicadas

19I.7.4 confirmó `missing_boundary_identity=0`: las 135 fronteras legítimas
revisadas siguen presentes. Quedaron 18 casos con la misma etiqueta repetida.

Este incremento intenta resolverlos sin mutar el corpus usando:
1. contención textual única;
2. solapamiento único de páginas;
3. abstención si la evidencia no es única.

## Implementación local

```powershell
pytest tests/test_legal_duplicate_boundary_audit_19i75.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_duplicate_boundaries_19i75
```

Salidas:
- `reports/sprint19I75/duplicate_boundary_audit.json`
- `reports/sprint19I75/duplicate_boundary_findings.csv`

No modifica 19C, candidato 19I.7, embeddings ni FAISS.
