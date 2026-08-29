# Sprint 19G — Acta de aceptación local

Estado inicial: **pendiente de ejecución en el repositorio local del usuario**.

## Evidencia requerida

- pruebas específicas de `test_legal_hybrid_retrieval.py`;
- Ruff limpio;
- mypy limpio;
- suite pytest completa;
- evaluación real sobre `runtime_artifacts_19f`;
- comparación 19F.1 -> 19G;
- consulta trazable de LIVA;
- consulta trazable de CPEUM;
- auditoría GitHub antes de cualquier publicación.

## Umbrales

| Métrica | 19F.1 | aceptación 19G |
| --- | ---: | ---: |
| PrimaryHit@K | 0.833 | > 0.833 |
| PrimaryMRR | 0.778 | > 0.778 |
| LIVA tasa | fuera top-5 | dentro top-5 |
| CPEUM principios | fuera top-10 | dentro top-5 |
| truncamiento | 0 % | se conserva; no se reconstruye índice |

Además, ninguna fuente primaria previamente recuperada en top-k puede sufrir
regresión.

La aceptación final se registra solo después de revisar las salidas reales.
