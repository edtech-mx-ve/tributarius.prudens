# Sprint 19I.18J.12.4 — promoción transaccional + RAG + benchmark

## Objetivo

Consumir exclusivamente el candidato J.12.3 aprobado con SHA-256:

`4d040043173c625ca09ed2ae954aa2bdf01993989f1a52997d7acbb067fee25c`

y ejecutar:

1. validación criptográfica del candidato;
2. reconstrucción completa de retrieval subchunks y FAISS en staging;
3. benchmark 19G contra el runtime de staging;
4. promoción de canonical, manifest, retrieval y runtime solo si el benchmark
   supera todos los umbrales;
5. snapshot del estado anterior para rollback.

La reconstrucción ocurre **antes** de mutar el canonical vigente.

## Umbrales mínimos

- Hit@1(any) >= 1.000
- Hit@3(any) >= 1.000
- Hit@K(any) >= 1.000
- MRR(any) >= 1.000
- PrimaryHit@1 >= 0.917
- PrimaryHit@3 >= 0.917
- PrimaryHit@K >= 1.000
- PrimaryMRR >= 0.938
- MeanUniqueDocs@K >= 2.333

## Implementación

Primero validar el patch:

```powershell
pytest tests/test_transactional_rag_promotion_19i18j12_4.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

Después ejecutar una sola vez:

```powershell
python -m scripts.promote_rebuild_benchmark_19i18j12_4
```

Por defecto se usa `--local-files-only`, apropiado porque el modelo exacto ya
fue utilizado en los rebuilds anteriores. Si el cache local hubiese sido
eliminado, el comando fallará sin mutar canonical/runtime.

## Seguridad transaccional

El script no acepta un `work-dir` preexistente. Un fallo de reconstrucción o
benchmark ocurre antes de la promoción. Durante promoción se crea un snapshot
del canonical, manifest, retrieval y runtime anteriores. Ante excepción en el
reemplazo se intenta restaurar el snapshot.

Los snapshots quedan bajo:

`dist/snapshots_19i18j12_4/`

No eliminarlos hasta cerrar Sprint 19.

## Criterios de aceptación

- SHA canonical final = SHA candidato J.12.3.
- parent_count = 2981.
- benchmark_passed = True.
- rollback_snapshot_created = True.
- canonical_mutation_performed = True.
- runtime_mutation_performed = True.
- public_release_allowed = False.

## Limitaciones

Este sprint certifica regresión técnica del RAG y promoción controlada. No
resuelve por sí solo vigencia temporal ni derechos de redistribución.
Git push, GitHub Release y Render continúan bloqueados.
