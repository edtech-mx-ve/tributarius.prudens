# Sprint 19E — Recuperación RAG real end-to-end local

## Objetivo

Validar el índice real construido en 19D con consultas fiscales concretas y medir:

- top-k y score FAISS;
- documento/fuente/unidad recuperada;
- Hit@1, Hit@3, Hit@K y MRR sobre un baseline reproducible;
- integridad de trazabilidad por `document_id`, `source_type`, unidad y páginas;
- riesgo de truncamiento comparando tokens reales de cada texto de embedding contra
  `max_seq_length` del modelo cargado.

Esta evaluación mide recuperación, no corrección jurídica final. Una consulta con el
`document_id` esperado en top-k puede seguir requerir validación del artículo, vigencia,
contexto y aplicabilidad normativa.

## Casos baseline

`app/resources/retrieval_eval_cases.json` contiene 12 consultas que cubren PRODECON,
UNAM y normativa: CPEUM, CFF, LISR, LIVA, RMF 2026, LIF 2026, LFPCA, LOTFJA, LIEPS y
LFISAN.

Los resultados iniciales se observan antes de fijar un umbral de aceptación. No se
inventa un umbral legal sin datos medidos.

## Consulta manual

```powershell
python -m scripts.query_runtime_rag `
  "¿Cuáles son los derechos y obligaciones de los contribuyentes?" `
  --top-k 5 `
  --local-files-only
```

Con filtro documental:

```powershell
python -m scripts.query_runtime_rag `
  "deducciones personales de personas físicas" `
  --document-id lisr `
  --top-k 5 `
  --local-files-only
```

## Evaluación baseline

```powershell
python -m scripts.evaluate_runtime_retrieval --local-files-only
```

## Diagnóstico exacto de truncamiento

```powershell
python -m scripts.evaluate_runtime_retrieval `
  --local-files-only `
  --diagnose-lengths
```

El diagnóstico usa el tokenizer del mismo Sentence Transformer y compara cada texto
real enviado al embedder con `model.max_seq_length`. Si existe una proporción relevante
de chunks por encima del límite, el siguiente incremento debe crear subchunks de
recuperación preservando la identidad del padre (`parent_chunk_id`) y la unidad jurídica.

## Criterios de aceptación

1. Los scripts cargan el índice 19D con verificación SHA-256.
2. Las 12 consultas se ejecutan sin error.
3. Se reportan Hit@1, Hit@3, Hit@K y MRR.
4. Cada hit manual expone score, fuente, documento, unidad y páginas.
5. El diagnóstico informa `model_max_seq_length`, chunks en riesgo y ratio real.
6. Ruff, mypy y pytest permanecen limpios.
7. El auditor de publicación permanece limpio.
8. No se hace commit/push/Render hasta aprobar localmente la calidad de recuperación.

## Limitaciones

- El baseline comprueba recuperación documental, no pertinencia jurídica exhaustiva.
- No mezcla jurisprudencia con normativa.
- No modifica el contenido de los 3174 chunks originales.
- No usa APIs comerciales, GPU ni servicios de pago.
