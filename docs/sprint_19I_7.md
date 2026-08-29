# Sprint 19I.7 — saneamiento semántico de unidades legales

## Objetivo

Eliminar falsos límites canónicos causados por referencias cruzadas que comienzan
una línea, sin alterar todavía el corpus 19C ni los artefactos 19F.

La regla estructural se endurece: un encabezado de artículo necesita un
identificador jurídico válido y un terminador propio de encabezado (`.-`, `.`,
`:`, guion tipográfico o fin de línea). Expresiones como `artículo 166 de la
Ley` o `artículo 31-A, primer párrafo` permanecen dentro del artículo padre.

Se soportan identificadores con sufijos por guion y `BIS`, `TER`, `QUÁTER`.

## Implementación

El candidato se reconstruye desde los Markdown normalizados mediante el pipeline
19C, pero se escribe exclusivamente en:

- `reports/sprint19I7/candidate_chunks.jsonl`
- `reports/sprint19I7/candidate_chunking_manifest.json`
- `reports/sprint19I7/semantic_canonical_report.json`

No se sobrescribe `knowledge/chunks/chunks.jsonl`. No se reconstruyen
subchunks 19F, embeddings ni FAISS.

### Ejecución local

```powershell
pytest tests/test_semantic_legal_units_19i7.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.build_semantic_canonical_candidate
```

Si ya existe una salida diagnóstica 19I.7 y se desea regenerarla deliberadamente:

```powershell
python -m scripts.build_semantic_canonical_candidate --overwrite-candidate
```

## Resultado esperado

El candidato debe ser válido, sin IDs duplicados ni textos vacíos. Es normal que
su cardinalidad difiera de 3174: precisamente se está midiendo cuántas unidades
19C nacieron de referencias cruzadas interpretadas como encabezados.

La promoción del candidato queda prohibida hasta revisar el informe por documento
y reejecutar las auditorías de integridad sobre la copia.
