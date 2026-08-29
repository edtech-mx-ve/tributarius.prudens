# Sprint 19I.15 — guard temporal de runtime

Integra el sidecar de procedencia temporal 19I.14 con el puente RAG → normativa.

El objetivo no es habilitar nuevas normas sino impedir que LIVA/CPEUM puedan ser
promovidas accidentalmente por metadatos temporales obsoletos mientras su vigencia
documental permanezca `unknown_fail_closed`.

## Comportamiento

- el runtime carga `knowledge/temporal/temporal_provenance_registry.json` si existe;
- si un documento tiene gap `document_wide_temporal_validity` con estado
  `unknown_fail_closed`, el puente RAG no lo promueve a candidato normativo;
- documentos no bloqueados conservan el comportamiento previo;
- si `REQUIRE_TEMPORAL_PROVENANCE_REGISTRY=true`, la ausencia del registro impide
  construir el runtime;
- no se infieren fechas ni se modifica FAISS.

## Implementación local

```powershell
pytest tests/test_normative_temporal_runtime_guard_19i15.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_guard_19i15
```

Después, mantener las pruebas E2E locales antes de cualquier push o Render.
