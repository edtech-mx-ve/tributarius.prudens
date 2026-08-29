# Sprint 19C — Estructuración jurídica y chunking del corpus real

## Objetivo

Transformar el corpus normalizado y validado en Sprints 19A/19B en unidades recuperables
con estructura jurídica, académica y de orientación. El resultado alimentará los
embeddings y FAISS del Sprint 19D.

## Entrada

- `knowledge/metadata/fiscal_corpus_15_manifest.json`
- `knowledge/metadata/prodecon_integration_manifest.json`
- 15 Markdown normalizados de Sprint 19B
- 12 Markdown de secciones PRODECON de Sprint 19A
- `app/resources/fiscal_corpus_15_catalog.json`

## Estrategias

- PRODECON: una unidad explícita por cada uno de sus 12 apartados.
- UNAM: capítulo académico.
- Leyes, Constitución y reglamentos: artículo.
- RMF 2026: regla administrativa numerada.
- Si un documento no expone la unidad esperada, el fallback usa encabezados Markdown.
- Si tampoco hay encabezados, se conserva como una sola unidad trazable.
- No se aplican ventanas arbitrarias de tokens ni solapamientos artificiales.

## Salidas

- `knowledge/chunks/chunks.jsonl`
- `knowledge/chunks/chunking_manifest.json`

Cada chunk conserva identificador determinista, documento, tipo de fuente, unidad,
jerarquía, páginas cuando están disponibles, materia, vigencia documental conocida,
SHA-256 del PDF origen y SHA-256 del texto del chunk.

## Implementación local

```powershell
python -m scripts.build_legal_chunks
```

Si ya existen artefactos y se desea regenerarlos deliberadamente:

```powershell
python -m scripts.build_legal_chunks --overwrite
```

## Pruebas

```powershell
pytest tests/test_legal_chunking.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

## Criterios de aceptación

1. Se procesan 16 documentos lógicos: PRODECON + UNAM + 14 normativos.
2. PRODECON produce exactamente 12 chunks explícitos.
3. RMF intenta segmentación por regla administrativa.
4. Leyes/reglamentos intentan segmentación por artículo.
5. UNAM intenta segmentación por capítulo.
6. No existen `chunk_id` duplicados.
7. `chunks.jsonl` y su manifiesto se escriben atómicamente.
8. El manifiesto reporta por documento los chunks estructurados y fallback.
9. Ruff, mypy y pytest permanecen limpios.
10. Toda la aceptación se realiza localmente antes de GitHub o Render.

## Limitaciones

- La calidad de segmentación depende de la estructura textual conservada durante PDF→MD.
- Un fallback estructural debe revisarse si representa una proporción relevante de un
  documento; el manifiesto lo hace visible.
- Este sprint no calcula embeddings ni crea FAISS.
- La presencia de fechas a nivel documento no sustituye el análisis de vigencia por
  artículo, regla o disposición transitoria.
