# Sprint 19I.4 — Auditoría causal 19C ↔ 19F

## Objetivo

Determinar si las contradicciones artículo↔texto detectadas en Sprint 19I.3
provienen del chunk canónico 19C o de la segmentación de recuperación 19F.

La auditoría es de solo lectura. No altera corpus, chunks, embeddings ni FAISS.

## Clases causales

- `canonical_parent_mismatch`: el chunk canónico ya contradice su metadata;
  requiere corrección en 19C.
- `retrieval_mismatch_parent_verified`: el padre canónico coincide con su
  artículo, pero el subchunk 19F empieza con otro artículo; requiere corregir
  segmentación 19F.
- `retrieval_continuation_parent_verified`: el subchunk no repite el encabezado,
  pero su padre canónico está verificado.
- `retrieval_match`: subchunk y metadata coinciden explícitamente.
- `canonical_parent_unverifiable`: no es posible demostrar correspondencia del
  padre con la comprobación estructural actual.
- `parent_missing`: el `parent_chunk_id` no existe en el corpus canónico.
- `non_article_unit`: unidades como reglas RMF. No se consideran fallos por no
  contener `Artículo`.

## Implementación

```powershell
python -m scripts.audit_normative_parent_integrity `
  --retrieval "deployment/runtime_artifacts_19f/chunks.jsonl" `
  --canonical "knowledge/chunks/chunks.jsonl" `
  --output-dir "reports/sprint19I4" `
  --expected-retrieval-total 29402 `
  --expected-canonical-total 3174
```

Genera:

- `normative_parent_audit_report.json`
- `normative_parent_audit_findings.csv`
- `repair_queue_19c.jsonl`
- `repair_queue_19f.jsonl`
- `parent_review_queue.jsonl`

## Criterios de aceptación

1. Pruebas específicas limpias.
2. Ruff limpio.
3. mypy limpio.
4. pytest completo limpio salvo warning externo conocido.
5. Se procesan 29,402 subchunks y 3,174 chunks canónicos.
6. RMF se clasifica como unidad no-artículo en lugar de falso fallo.
7. La auditoría separa defectos de 19C y 19F sin modificar artefactos.
8. No se reconstruye FAISS hasta revisar las colas reales de reparación.

## Limitaciones

La comparación se centra en artículos explícitos. Fracciones, incisos,
transitorios y reglas administrativas requieren validadores específicos.
`retrieval_continuation_parent_verified` demuestra consistencia con el padre
solo a nivel estructural; no sustituye validación jurídica sustantiva.
