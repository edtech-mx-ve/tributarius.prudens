# Sprint 19I.13 — verificación contextual de candidatos temporales

19I.12 encontró 80 líneas prioritarias de LIVA/CPEUM, pero únicamente 2 contienen
una fecha explícita. Este sprint no promueve esas fechas: extrae contexto alrededor
de cada línea y determina si la evidencia parece corresponder al documento completo,
a una reforma/decreto/unidad específica o si el alcance sigue ambiguo.

`promotion_ready=0` permanece como invariante fail-closed.

## Implementación local

```powershell
pytest tests/test_normative_temporal_candidate_verifier_19i13.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.verify_temporal_candidates_19i13
```

Salidas:

- `reports/sprint19I13/temporal_candidate_verification.json`
- `reports/sprint19I13/temporal_candidate_verification.csv`

No modifica catálogo, corpus, chunks, embeddings, FAISS ni runtime.
