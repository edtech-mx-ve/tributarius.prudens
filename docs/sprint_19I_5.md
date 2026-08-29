# Sprint 19I.5 — Refinamiento causal de límites legales

## Objetivo

Refinar los 2,896 casos que 19I.4 clasificó como
`retrieval_mismatch_parent_verified` para distinguir:

- un encabezado secundario real de artículo dentro del padre canónico;
- una referencia cruzada del tipo `artículo 5 de esta Ley`;
- los dos padres canónicos cuyo inicio ya está desalineado;
- casos que no pueden resolverse automáticamente con evidencia suficiente.

El incremento es diagnóstico y fail-closed. No muta Markdown, chunks canónicos,
subchunks, embeddings ni FAISS.

## Regla de detección

Una mención `Artículo N` no es automáticamente un límite jurídico. Para
considerarla encabezado fuerte debe:

1. iniciar una línea;
2. contener un identificador de artículo válido;
3. presentar un separador típico de encabezado (`.-`, `.`, `-`, `—`, `–`, `:`);
4. aparecer al comienzo del subchunk;
5. existir también como encabezado secundario dentro del padre canónico.

Si la mención aparece en prosa o como `Artículo 5 de esta Ley`, se clasifica
como `cross_reference_false_positive`.

## Salidas

- `legal_boundary_refinement_report.json`
- `legal_boundary_refinement_findings.csv`
- `true_secondary_boundaries.jsonl`
- `cross_reference_false_positives.jsonl`
- `canonical_start_mismatches.jsonl`
- `unresolved_boundaries.jsonl`

## Implementación

```powershell
python -m scripts.refine_normative_boundaries `
  --retrieval "deployment/runtime_artifacts_19f/chunks.jsonl" `
  --canonical "knowledge/chunks/chunks.jsonl" `
  --output-dir "reports/sprint19I5" `
  --expected-retrieval-total 29402 `
  --expected-canonical-total 3174
```

## Criterios de aceptación

1. Pruebas específicas limpias.
2. Ruff limpio.
3. mypy limpio.
4. pytest completo limpio salvo warning externo conocido.
5. Se procesan exactamente 29,402 subchunks y 3,174 chunks canónicos.
6. RMF permanece en `non_article_unit`.
7. Una referencia cruzada no se promueve a límite legal.
8. Los padres CFF/LIVA ya detectados permanecen en la cola de inicio canónico.
9. No se modifica ni reconstruye FAISS.
10. La reparación posterior usa solo las colas refinadas, no los 2,896 casos
    crudos de 19I.4.

## Limitaciones

La heurística reconoce encabezados de artículo con separadores comunes del
corpus mexicano. OCR o extracción con encabezados gravemente dañados puede caer
en `unresolved`. Esa categoría requiere revisión o una regla documental
específica antes de modificar el corpus.
