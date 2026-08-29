# Sprint 19F.1 — Endurecimiento de evaluación jurídico-documental

## Objetivo

No modifica embeddings, subchunking ni FAISS. Endurece la evaluación para que
una fuente doctrinal o de orientación no pueda ocultar la ausencia de la fuente
principal esperada.

## Cambios

- `expected_primary_document_ids`
- `expected_supporting_document_ids`
- métricas `PrimaryHit@1`, `PrimaryHit@3`, `PrimaryHit@K` y `PrimaryMRR`
- diversidad documental `MeanUniqueDocs@K`
- compatibilidad con `expected_document_ids` de Sprint 19E
- etiqueta configurable del evaluador mediante `--label`
- comparación 19E vs 19F basada también en fuentes principales

El caso `cpeum_principios` exige CPEUM como fuente principal y conserva UNAM
como apoyo. `liva_tasa` exige LIVA como fuente principal. Esto hace visibles
las dos deficiencias que la métrica agregada anterior podía ocultar.

## Implementación

Expandir el ZIP sobre la raíz del repositorio y ejecutar primero:

```powershell
pytest tests/test_retrieval_primary_sources.py -v
pytest tests/test_runtime_retrieval_evaluation.py -v
ruff check . --fix
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

No se reconstruye FAISS.

Luego evaluar el índice 19F existente:

```powershell
python -m scripts.evaluate_runtime_retrieval `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --label "19F.1" `
  --local-files-only `
  --diagnose-lengths
```

Comparar:

```powershell
python -m scripts.compare_runtime_retrieval_19f `
  --local-files-only
```

Para inspección manual de las regresiones:

```powershell
python -m scripts.query_runtime_rag `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --query "Ley del IVA tasa general impuesto al valor agregado actos gravados" `
  --top-k 10 `
  --local-files-only

python -m scripts.query_runtime_rag `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --query "principios constitucionales tributarios proporcionalidad equidad legalidad contribuciones" `
  --top-k 10 `
  --local-files-only
```

## Criterio de salida

19F.1 es diagnóstico. Si LIVA o CPEUM siguen fuera del top-k, no se manipula el
benchmark ni se vuelve a subchunkear. La acción siguiente será recuperación
híbrida/reranking con prioridad por fuente y autoridad jurídica, evaluada contra
el mismo conjunto congelado.
