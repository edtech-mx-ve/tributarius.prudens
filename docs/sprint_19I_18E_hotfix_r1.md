# Sprint 19I.18E hotfix r1

Corrige la identidad documental de PRODECON en la política de publicación.

El runtime semántico v2 usa `prodecon_contribuyente`, no `prodecon`. El
auditor funcionó correctamente al detectar la discrepancia como
`missing_policy_entry`.

## Cambio

- `prodecon` -> `prodecon_contribuyente`;
- se añade una prueba que fija exactamente los 16 `document_id` esperados;
- la política continúa fail-closed: los 16 documentos permanecen
  `unknown_requires_review`.

No se cambia ningún permiso, licencia, corpus, índice FAISS, vigencia temporal
ni artefacto de release.

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

Resultado esperado del auditor real:

- `observed_documents=16`
- `policy_documents=16`
- `missing_policy_documents=0`
- `verified_documents=0`
- `blocked_documents=16`
- `public_release_allowed=False`
- código de salida `3`
