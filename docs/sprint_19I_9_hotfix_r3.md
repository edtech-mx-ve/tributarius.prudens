# Sprint 19I.9 hotfix r3

El smoke posterior a r2 mostró dos fallos reales:

- CPEUM terminaba en `status=error`.
- LIEPS seguía fuera del top-5 de una consulta natural.

Correcciones:

1. El score público de `RetrievalHit` vuelve a quedar acotado a `[0, 1]`.
   El score compuesto aditivo permanece completo en `LegalScoreTrace.final_score`.
   Esto evita que la capa de trazabilidad rechace evidencia con score > 1.
2. Toda fuente jurídicamente ruteada conserva cobertura mínima en top-k:
   si queda fuera, sustituye únicamente el último resultado no ruteado.
   No se fuerza rango 1.
3. El smoke lee `applicable_normative_refs`, que es el contrato real del presenter.
4. Se agrega un diagnóstico directo que no oculta la excepción bajo la respuesta web.

No se reconstruyen embeddings ni FAISS.

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
