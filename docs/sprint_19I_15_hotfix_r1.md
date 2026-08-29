# Sprint 19I.15 hotfix r1

Corrección estática reportada por Ruff `I001`:

- se ordenan los imports de `app/services/runtime_factory.py`.

No cambia la lógica del guard temporal, el puente RAG → normativa, la configuración,
ni la política `unknown_fail_closed`.

## Implementación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_guard_19i15
```
