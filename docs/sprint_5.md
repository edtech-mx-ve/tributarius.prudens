# Sprint 5 — Retriever + evaluación RAG

## Objetivo

Consumir los índices FAISS del Sprint 4 mediante un retriever trazable y añadir una
evaluación offline reproducible de la recuperación antes de integrar Llama.

## Flujo

`consulta → embedding CPU → FAISS → filtros jurídicos deterministas → Top-K → evidencia`

La normativa y la jurisprudencia continúan siendo capas diferenciadas mediante
`source_type`; un filtro de jurisprudencia nunca se interpreta como normativa.

## Filtros disponibles

- `source_type`
- `chunk_type`
- `fiscal_year`
- `version_label`
- `document_id`

Los filtros se aplican sobre metadatos validados. Cuando existen filtros selectivos se
consulta el índice completo para no perder candidatos elegibles en esta línea base
exacta `IndexFlatIP`.

## Integridad

El retriever verifica SHA-256 de `index.faiss` y `chunks.jsonl`, correspondencia de
cantidad de vectores, dimensión y modelo de embeddings antes de recuperar evidencia.

## Evaluación

Dataset JSONL etiquetado manualmente:

```json
{"query_id":"q001","query":"...","relevant_chunk_ids":["chunk-id-1"]}
```

Métricas:

- Recall@K
- Precision@K
- MRR
- Hit Rate

No se inventan casos de evaluación jurídicos. El dataset real debe construirse con
consultas y relevancias revisadas.

## Comandos

```powershell
python -m scripts.search_vector_index `
  --index-dir ".\indexes\normativa" `
  --query "¿Cuáles son las obligaciones aplicables?" `
  --top-k 5 `
  --source-type normativa `
  --fiscal-year 2026 `
  --local-files-only
```

```powershell
python -m scripts.evaluate_retrieval `
  --index-dir ".\indexes\normativa" `
  --dataset ".\rag\evaluation\datasets\normativa_eval.jsonl" `
  --k 5 `
  --local-files-only
```

## Criterios de aceptación

1. Carga segura y validada del índice.
2. Verificación SHA-256.
3. Compatibilidad estricta del modelo de consulta con el modelo del índice.
4. Top-K reproducible.
5. Filtros jurídicos deterministas.
6. Normativa y jurisprudencia diferenciadas por metadatos.
7. Recall@K, Precision@K, MRR y Hit Rate implementados y probados.
8. Tests offline sin descargar modelos.
9. Sin LLM ni API comercial.
10. Errores no exponen texto fiscal en logs.

## Limitaciones

- Aún no hay búsqueda léxica/BM25 ni fusión híbrida semántico-léxica.
- Aún no hay generación con Llama; corresponde a sprints posteriores.
- La evaluación real requiere un conjunto de relevancia revisado por humanos.
- `Precision@K` usa K como denominador aun cuando el retriever devuelva menos de K.
- Los filtros actuales operan sobre metadatos presentes en `ChunkMetadata`; materia y
  vigencia normativa completa se incorporarán al conectar el motor normativo.
