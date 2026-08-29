# Sprint 19I.10 — conmutación local del runtime por defecto

Sprint 19I.9 validó el runtime semántico v2 E2E:

- LIVA: evidencia esperada presente.
- CPEUM: evidencia esperada presente.
- LIEPS: evidencia esperada presente.
- `/ready`, `/health` y `/` operativos.
- benchmark 19G sin regresión.

19I.10 cambia el valor por defecto de `RAG_ARTIFACT_DIR` a:

`deployment/runtime_artifacts_semantic_v2`

No elimina ni sobrescribe `runtime_artifacts_19f`.
No modifica embeddings ni FAISS.

## Implementación local

```powershell
pytest tests/test_default_semantic_runtime_19i10.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_default_runtime_19i10
```

El smoke elimina cualquier override `RAG_ARTIFACT_DIR` del proceso para verificar
que la aplicación realmente use el nuevo valor por defecto.
