# Sprint 19D — Embeddings reales + FAISS CPU

## Objetivo

Construir localmente los artefactos RAG de runtime a partir de los 3174 chunks
jurídicos y doctrinales aprobados en Sprint 19C, usando únicamente software
gratuito/open source:

- Sentence Transformers en CPU.
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- FAISS CPU con similitud coseno implementada mediante `IndexFlatIP` sobre
  vectores normalizados.

## Entrada

`knowledge/chunks/chunks.jsonl`

El builder admite tanto el esquema histórico de `app.domain.chunks.LegalChunk`
como el esquema enriquecido de Sprint 19C. Los chunks 19C se adaptan al esquema
de runtime sin perder los metadatos esenciales de trazabilidad.

## Salida

`deployment/runtime_artifacts/`

- `index.faiss`
- `chunks.jsonl`
- `manifest.json`

El manifiesto registra modelo, dimensión, cardinalidad, SHA-256, tamaños,
duración de construcción, pico de memoria Python medido con `tracemalloc` y
longitud máxima de texto enviado al embedder.

## Seguridad y reproducibilidad

- CPU solamente.
- `trust_remote_code=False`.
- No se usan APIs comerciales.
- No se ejecuta código remoto.
- `--local-files-only` permite exigir un modelo ya presente en caché.
- No se sobrescriben artefactos sin `--overwrite`.
- Se verifican IDs únicos, hashes, cardinalidad y dimensión.
- El índice se genera primero en un directorio temporal y se publica de forma
  atómica al destino final.

## Limitación conocida

`tracemalloc` mide memoria administrada por Python y no toda la memoria nativa
consumida por PyTorch/Sentence Transformers/FAISS. El benchmark local debe
interpretar ese valor como cota parcial, no como RSS total del proceso.

Los chunks jurídicos preservan unidades legales y académicas. Algunos capítulos
o secciones son extensos y el modelo de embeddings puede truncar internamente
secuencias por su límite de contexto. Esta limitación debe medirse en la
evaluación de recuperación del siguiente incremento antes de considerar el RAG
apto para producción.

## Criterios de aceptación

1. El builder consume exactamente 3174 chunks del corpus Sprint 19C.
2. `index.faiss`, `chunks.jsonl` y `manifest.json` existen.
3. `manifest.chunk_count == 3174`.
4. `FAISS.ntotal == 3174`.
5. `FAISS.d == manifest.vector_dimension`.
6. Los SHA-256 de índice y chunks coinciden con el manifiesto.
7. Ruff, mypy y pytest permanecen limpios.
8. Auditoría GitHub permanece limpia.
9. No se hace commit/push/Render hasta aprobar toda la validación local.

## Implementación

Desde la raíz del repositorio:

```powershell
python -m scripts.build_runtime_rag --overwrite
python -m scripts.validate_runtime_rag
```

La primera ejecución puede descargar el modelo público de Sentence Transformers.
Para exigir caché local:

```powershell
python -m scripts.build_runtime_rag --overwrite --local-files-only
```

Resultado esperado:

```text
OK: Sprint 19D; índice FAISS CPU construido
- chunks=3174
...
OK: artefactos RAG íntegros
- chunks=3174
- faiss_ntotal=3174
```
