# Sprint 19I.7.6 — aislamiento del último caso ambiguo

19I.7.5 resolvió 17 de 18 etiquetas duplicadas y dejó un solo caso
`unresolved_multiple_content_matches`.

Este incremento es estrictamente diagnóstico. Para cada candidata con la misma
etiqueta registra:

- `chunk_id`;
- páginas;
- hash textual;
- contención exacta en ambos sentidos;
- longitud del prefijo compartido;
- extractos comparables.

## Implementación local

```powershell
pytest tests/test_legal_unresolved_boundary_audit_19i76.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_unresolved_boundary_19i76
```

Salidas:

- `reports/sprint19I76/unresolved_boundary_audit.json`
- `reports/sprint19I76/unresolved_boundary_candidates.csv`

No modifica corpus, candidato, embeddings ni FAISS.
