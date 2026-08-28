# Sprint 16 — Evaluación integral

## Objetivo

Convertir la evaluación en una capa explícita, reproducible y trazable que
mida el comportamiento del sistema completo, no una métrica aislada.

## Alcance

Se incorporó `evaluation/` con contratos tipados, carga segura de datasets,
métricas puras, evaluación de `CanonicalExecutionResult`, análisis de errores,
exportación JSON controlada y CLI offline.

El evaluador cubre:

- exactitud de intención;
- Recall@K de recuperación;
- precisión y recall de IDs de cita;
- exactitud de referencias normativas aplicables;
- exactitud de reglas activadas;
- exactitud de valores de cálculo;
- decisión de revisión humana;
- abstención;
- consistencia de trazabilidad.

## Umbrales iniciales

Los umbrales son explícitos y versionables mediante `EvaluationThresholds`:

| Métrica | Umbral |
| --- | ---: |
| intent_accuracy | 0.90 |
| retrieval_recall_at_k | 0.80 |
| citation_precision | 0.95 |
| citation_recall | 0.80 |
| normative_accuracy | 0.95 |
| rule_accuracy | 0.95 |
| calculation_accuracy | 1.00 |
| review_accuracy | 0.95 |
| abstention_accuracy | 0.95 |
| trace_consistency | 1.00 |

Estos valores son criterios de ingeniería iniciales, no evidencia de calidad
jurídica hasta disponer de un dataset humano representativo.

## Dataset

`evaluation/datasets/integral_smoke.json` es exclusivamente sintético. Su
objetivo es verificar el evaluador de extremo a extremo. No constituye
benchmark fiscal mexicano ni dataset jurídico de producción.

El loader exige JSON UTF-8, máximo 5 MiB, IDs únicos y esquema cerrado. El
reporte conserva SHA-256 del dataset para reproducibilidad.

## Smoke integral

```powershell
python -m scripts.evaluate_integral `
  --dataset ".\evaluation\datasets\integral_smoke.json" `
  --manifest ".\evaluation\datasets\integral_smoke_results.json" `
  --output ".\evaluation\reports\integral_smoke_report.json" `
  --overwrite
```

Resultado esperado:

`OK: 1/1 casos; overall_passed=True.`

El CLI devuelve código 0 si se superan los criterios, 2 si la evaluación es
válida pero falla los criterios y 1 ante errores de entrada/ejecución.

## Análisis de errores

Cada caso conserva métricas y fallos. El reporte agrega buckets por tipo de
fallo para evitar que un promedio oculte errores críticos. Un cálculo
incorrecto, una norma incorrecta o una traza inconsistente son observables de
forma separada.

## Fidelidad de citas

La evaluación actual comprueba que los IDs citados sean los esperados y que
sean consistentes con la evidencia trazada. Esto no demuestra por sí solo que
cada afirmación textual esté semánticamente respaldada por la fuente.

La evaluación de fidelidad semántica debe realizarse con un dataset anotado y
revisión humana; no se presenta un juez LLM como verdad jurídica.

## LLM

El smoke usa el proveedor mock para reproducibilidad y coste cero. La evaluación
con Llama real debe ejecutarse como suite separada cuando se seleccione el
modelo definitivo, conservando modelo, parámetros, semilla cuando aplique,
contexto y artefactos de entrada.

## Robustez y seguridad

Los datasets de evaluación son datos no confiables: esquema cerrado, tamaño
limitado y sin ejecución dinámica. No se usa `eval`, `exec` ni carga de código.
Los reportes no se sobrescriben salvo autorización explícita.

## Limitaciones

- El smoke sintético prueba infraestructura, no exactitud fiscal real.
- No existe todavía gold set humano representativo.
- La fidelidad semántica de afirmaciones requiere anotación humana.
- No hay baseline BM25/lexical todavía.
- Los filtros RAG jurídicos aún deben ampliarse.
- La evaluación jurisprudencial se incorpora en Sprints 17 y 18.
- El modelo Llama definitivo aún debe benchmarkearse.

## Criterios de aceptación

- suite completa de pruebas sin fallos;
- Ruff limpio;
- mypy limpio;
- smoke integral `overall_passed=True`;
- mutaciones de cita, norma, cálculo y traza son detectadas;
- casos de abstención son evaluables;
- reporte JSON incluye SHA-256, métricas, casos, errores y limitaciones.
