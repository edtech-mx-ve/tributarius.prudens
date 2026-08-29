# Sprint 19I.16 hotfix r3

Corrige el criterio del smoke E2E.

El guard temporal bloquea la promoción normativa de los documentos con
`unknown_fail_closed`; no bloquea otras normas recuperadas en la misma consulta.

Por tanto, una consulta sobre LIVA puede tener `applicable_normative_refs > 0`
si esas referencias pertenecen, por ejemplo, a RMF/LIF u otra fuente temporalmente
válida. El criterio correcto es:

- LIVA/CPEUM deben aparecer como evidencia RAG cuando corresponda;
- ninguna referencia aplicable puede pertenecer a LIVA/CPEUM mientras estén
  bloqueadas;
- otras referencias normativas aplicables pueden coexistir.

## Implementación local

```powershell
pytest tests/test_temporal_runtime_e2e_contract_19i16.py -v
pytest tests/test_temporal_runtime_e2e_smoke_parser_19i16.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_e2e_19i16
```
