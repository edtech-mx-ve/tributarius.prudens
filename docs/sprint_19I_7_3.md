# Sprint 19I.7.3 — auditoría fuente ↔ parser

19I.7.2 mostró 135 fronteras absorbidas con apariencia de artículo legítimo.
Antes de modificar otra vez el parser, este incremento localiza la primera línea
real de cada chunk 19C en el Markdown normalizado y prueba si la expresión actual
`_ARTICLE_RE` debería reconocerla.

Esto separa dos causas:

- `parser_should_split_but_did_not`: la línea fuente sí satisface el parser; el
  problema está en otra etapa de estructuración/chunking.
- `source_heading_variant_not_supported`: la forma real del encabezado no está
  contemplada por la regla 19I.7.
- `source_line_not_found`: el texto 19C ya no coincide directamente con Markdown
  y requiere inspección de normalización/proveniencia.

## Implementación local

```powershell
pytest tests/test_legal_heading_source_audit_19i73.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_heading_sources_19i73
```

Salidas:

- `reports/sprint19I73/heading_source_audit.json`
- `reports/sprint19I73/heading_source_findings.csv`

No modifica corpus, candidato, embeddings ni FAISS.
