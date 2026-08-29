# Sprint 19I.8 — reconstrucción RAG desde corpus semántico v2

El corpus promovido de 2981 chunks sustituye únicamente como fuente de build al
baseline 19C. Este incremento no cambia todavía el runtime activo.

Pipeline local:

`chunks_semantic_v2.jsonl -> retrieval subchunks -> embeddings CPU -> FAISS`

Salidas nuevas y aisladas:

- `knowledge/retrieval_chunks_semantic_v2/`
- `deployment/runtime_artifacts_semantic_v2/`

El script valida antes de construir:

- estado `approved_semantic_canonical`;
- 2981 padres;
- JSONL válido;
- SHA-256 igual al manifiesto de promoción.

## Implementación

```powershell
python -m scripts.rebuild_semantic_runtime_19i8 --local-files-only
python -m scripts.evaluate_semantic_runtime_19i8 --local-files-only
```

La reconstrucción puede tardar varios minutos en CPU. No interrumpir el proceso
mientras esté creando embeddings/FAISS.
