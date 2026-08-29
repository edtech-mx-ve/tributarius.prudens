# Sprint 19I.9 hotfix r4

Corrección no funcional del script de diagnóstico:

- orden/formato de import compatible con Ruff;
- estrechamiento de tipo para `applicable_normative_refs` antes de `len()`;
- sin cambios en recuperación, scores, embeddings, FAISS ni runtime.

## Implementación local

```powershell
pytest tests/test_semantic_runtime_smoke_19i9.py tests/test_legal_hybrid_retrieval.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.evaluate_semantic_runtime_19i8 --local-files-only
python -m scripts.diagnose_semantic_runtime_19i9 --local-files-only
python -m scripts.smoke_semantic_runtime_19i9 --local-files-only
```
