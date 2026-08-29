# Sprint 19I.18E hotfix r2

Corrige exclusivamente Ruff/I001 en
`tests/test_runtime_publication_policy_19i18e.py`.

La causa es el espaciado entre el bloque de imports y la constante de módulo.

No modifica:
- la política fail-closed;
- los 16 `document_id`;
- estados de redistribución;
- evidencia;
- corpus;
- FAISS;
- runtime;
- plan de publicación.

## Validación

```powershell
pytest tests/test_runtime_publication_safety_audit_19i18e.py -v
pytest tests/test_runtime_publication_policy_19i18e.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```
