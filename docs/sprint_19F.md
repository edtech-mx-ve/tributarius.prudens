# Sprint 19F — Subchunking jurídico trazable y reindexación

## Problema confirmado por Sprint 19E

El baseline real produjo Hit@1=0.583, Hit@3=0.667, Hit@K=0.750 y MRR=0.646.
El tokenizer del modelo informó `max_seq_length=128`; 2815 de 3174 chunks
(88.7 %) exceden ese límite. Por ello, el índice 19D es íntegro, pero gran parte
de la evidencia no participa en el embedding efectivo.

## Decisión

Los 3174 chunks de Sprint 19C/19D permanecen como unidades jurídicas canónicas.
Sprint 19F crea subchunks únicamente para recuperación. Cada subchunk conserva
`parent_chunk_id`, documento, tipo de fuente, unidad jurídica, páginas, vigencia
y hash, además de índice y cantidad de subchunks.

La división prioriza párrafos y oraciones. Solo cuando una unidad elemental aún
excede el presupuesto se aplica división por palabras con solapamiento
controlado. Cada texto final se valida con el tokenizer real sobre
`render_embedding_text()`. Criterio estructural: cero subchunks por encima del
`max_seq_length` del modelo.

## Artefactos

Se preserva el baseline 19D/19E:

- `deployment/runtime_artifacts/`

Se generan artefactos nuevos para 19F:

- `knowledge/retrieval_chunks/retrieval_chunks.jsonl`
- `knowledge/retrieval_chunks/retrieval_chunks_manifest.json`
- `deployment/runtime_artifacts_19f/index.faiss`
- `deployment/runtime_artifacts_19f/chunks.jsonl`
- `deployment/runtime_artifacts_19f/manifest.json`

No se sobrescribe el índice baseline durante la comparación.

## Implementación local

```powershell
python -m scripts.build_retrieval_subchunks `
  --local-files-only `
  --overwrite
```

Criterios inmediatos:

- padres = 3174;
- cobertura_padres = 3174;
- `chunks_risk = 0`;
- `max_rendered_tokens <= 128`.

Después:

```powershell
python -m scripts.build_runtime_rag_19f `
  --local-files-only `
  --overwrite
```

Evaluación del candidato:

```powershell
python -m scripts.evaluate_runtime_retrieval `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --local-files-only `
  --diagnose-lengths
```

Comparación directa:

```powershell
python -m scripts.compare_runtime_retrieval_19f `
  --local-files-only
```

## Criterios de aceptación

1. Los 3174 padres canónicos están representados.
2. Cero textos de embedding 19F exceden el límite real del modelo.
3. Los IDs de subchunks son únicos y deterministas.
4. Se conserva `parent_chunk_id` y trazabilidad jurídica.
5. Hit@K y MRR mejoran simultáneamente respecto a 19E.
6. Se inspeccionan específicamente los casos previamente fallidos: UNAM
   interpretación, CPEUM principios, CFF/RFC y LISR deducciones.
7. Ruff, mypy, pytest y auditoría GitHub permanecen limpios.
8. No se publica en GitHub/Render hasta aprobar localmente 19F.

## Limitaciones

El subchunking corrige truncamiento, pero no garantiza por sí solo la mejor
jerarquización normativa. Si la recuperación sigue dominada por reglamentos o
documentos semánticamente próximos, el siguiente ajuste debe ser híbrido
(vectorial + léxico + priorización/reranking por tipo de fuente), medido sobre
el mismo benchmark.
