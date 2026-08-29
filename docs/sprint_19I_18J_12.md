# Sprint 19I.18J.12 — plan de reconstrucción selectiva

## Evidencia de entrada

J.11 confirmó diferencias textuales materiales en:

- LFDC, similitud aproximada 0.99342201;
- Reglamento LIVA 250914, similitud aproximada 0.94922443.

La igualdad de páginas no compensa la diferencia textual. Ambos documentos
deben tratarse como corpus local potencialmente desactualizado respecto de la
evidencia oficial descargada.

## Objetivo

Crear una autorización técnica explícita y limitada para reconstruir solamente
los documentos afectados. Este sprint **no ejecuta todavía la mutación**.

Secuencia prevista:

1. snapshot de artefactos actuales;
2. fuente nueva = PDF oficial ya verificado por el importador;
3. extracción y Markdown normalizado;
4. detección de estructura legal;
5. parent chunks solo del documento;
6. subchunks solo del documento;
7. reconstrucción atómica del índice runtime;
8. regresión retrieval/RAG;
9. repetición de gates temporal y de publicación.

## Invariantes

Los otros documentos no pueden cambiar como efecto colateral. La reconstrucción
no concede derechos de redistribución ni resuelve vigencia temporal.

## Implementación

```powershell
python -m scripts.plan_selective_rebuild_19i18j12
```

Luego:

```powershell
pytest tests/test_runtime_selective_rebuild_plan_19i18j12.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

Resultado esperado:

- `target_documents=lfdc,reg_liva_250914`
- `target_count=2`
- `rebuild_authorized=True`
- `rebuild_executed=False`
- `public_release_allowed=False`

## Siguiente incremento

J.12.1 implementará la reconstrucción transaccional/selectiva reutilizando el
pipeline existente del repositorio, después de validar las rutas y formatos
reales de sus artefactos.
