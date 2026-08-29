# Sprint 19I.15 hotfix r2

Corrección del segundo `I001` de Ruff en `app/services/runtime_factory.py`.

El orden de imports ya era correcto tras r1. Ruff seguía marcando el bloque porque
existían dos líneas en blanco entre el último import y `_REQUIRED_RAG_FILES`.
Este hotfix deja una sola línea en blanco, que es el formato exigido por la
configuración actual del proyecto.

No cambia lógica funcional.

## Implementación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_guard_19i15
```
