# Sprint 19I.16 hotfix r1

Corrección estática reportada por Ruff `E501` en el smoke E2E.

- Se divide la consulta CPEUM en dos literales adyacentes.
- No cambia la consulta efectiva ni la lógica del smoke.
- No modifica runtime, corpus, FAISS, metadatos ni política temporal.

## Implementación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_e2e_19i16
```
