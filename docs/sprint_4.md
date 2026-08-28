# Sprint 4 — Embeddings + FAISS CPU

## Objetivo

Convertir los chunks jurídicos estructurados del Sprint 3 en embeddings semánticos
normalizados y persistirlos en un índice FAISS CPU reproducible y verificable.

## Stack

- Sentence Transformers.
- Modelo predeterminado:
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- NumPy.
- FAISS CPU.
- Similaridad coseno implementada como producto interno sobre vectores L2 normalizados.

No se usan APIs comerciales, GPU, claves ni servicios de pago.

## Flujo

`JSONL de chunks → texto enriquecido con contexto jurídico → embeddings CPU →
normalización L2 → FAISS IndexFlatIP → index.faiss + chunks.jsonl + manifest.json`

El texto embebido conserva contexto de fuente, documento, título, capítulo, sección,
artículo, fracción e inciso antes del texto principal. El contenido original del chunk
no se modifica.

## Artefactos

Cada directorio de índice contiene:

- `index.faiss`: índice binario.
- `chunks.jsonl`: mapping posicional estable entre FAISS y los chunks.
- `manifest.json`: modelo, dimensión, métrica, cantidad de chunks y hashes SHA-256.

Se evita `pickle` para no introducir deserialización insegura.

## Seguridad y robustez

- CPU obligatorio.
- `trust_remote_code=False`.
- Validación conservadora del identificador del modelo.
- Rechazo de embeddings vacíos, NaN, infinito o norma cero.
- Rechazo de `chunk_id` duplicados.
- Sin sobrescritura silenciosa.
- Integridad verificable mediante SHA-256.
- `--local-files-only` para entornos sin red o para exigir modelo previamente cacheado.
- Logs sin contenido fiscal ni texto de usuario.

## Construcción

```powershell
python -m scripts.build_faiss_index `
  --chunks ".\knowledge\chunks\normativa\documento.jsonl" `
  --output-dir ".\indexes\normativa"
```

La primera ejecución del modelo puede descargar sus pesos gratuitos. Después puede
usarse `--local-files-only`.

## Verificación

```powershell
python -m scripts.verify_vector_index `
  --index-dir ".\indexes\normativa"
```

## Criterios de aceptación

1. Se generan embeddings exclusivamente en CPU.
2. Los vectores se normalizan antes del indexado.
3. FAISS usa `IndexFlatIP` para similitud coseno exacta.
4. La posición de cada vector conserva mapping 1:1 con `chunks.jsonl`.
5. Se genera manifiesto con dimensión, modelo, hashes y cantidad.
6. No existe sobrescritura silenciosa.
7. Los IDs duplicados bloquean la construcción.
8. Los tests no descargan modelos ni dependen de red.
9. La implementación puede ejecutarse en Windows con Python 3.12.
10. Sprint 5 podrá consumir el índice sin rehacer el corpus.

## Limitaciones

- El modelo predeterminado es una línea base multilingüe, no un modelo jurídico
  especializado.
- Sprint 4 no implementa todavía el retriever híbrido, filtros jurídicos ni métricas
  Recall@K/MRR; corresponden al Sprint 5.
- `IndexFlatIP` prioriza exactitud y simplicidad. Para corpus mucho mayores podrá
  evaluarse HNSW/IVF sin cambiar el contrato del pipeline.
- La descarga inicial del modelo depende de disponibilidad de red; el funcionamiento
  posterior puede ser local.
