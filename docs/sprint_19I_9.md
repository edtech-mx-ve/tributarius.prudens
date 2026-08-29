# Sprint 19I.9 — activación local controlada del runtime semántico

El benchmark de 19I.8 reprodujo exactamente las métricas de 19G:

- PrimaryHit@1 = 0.917
- PrimaryHit@3 = 0.917
- PrimaryHit@K = 1.000
- PrimaryMRR = 0.938
- MeanUniqueDocs@K = 2.333

Este incremento no cambia todavía el valor por defecto de producción.
Activa `deployment/runtime_artifacts_semantic_v2` únicamente dentro del
proceso del smoke y verifica:

- `/ready`
- `/health`
- `/`
- `POST /api/v1/consultations`
- consultas LIVA, CPEUM y LIEPS
- evidencia documental esperada
- estado `ready`

## Implementación local

```powershell
pytest tests/test_semantic_runtime_smoke_19i9.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_semantic_runtime_19i9 --local-files-only
```

No hay GitHub ni Render en este incremento.
