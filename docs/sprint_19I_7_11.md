# Sprint 19I.7.11 — frontera según perfil real

19I.7.10 dejó 14 casos `source_line_merged_under_neighbor_requires_review`.

La auditoría anterior era deliberadamente amplia: consideraba patrones genéricos
de Markdown/estructura como señales de parser. Sin embargo, `structure_document`
solo crea una nueva unidad cuando `_detect_boundary(line, profile)` la acepta
para el perfil real del documento.

19I.7.11 corrige esa diferencia conceptual usando el `chunking_profile` del
catálogo fiscal y el mismo `_detect_boundary` que genera el candidato.

No modifica corpus, candidato, embeddings ni FAISS.

## Implementación local

```powershell
pytest tests/test_legal_profile_boundary_audit_19i711.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_profile_boundaries_19i711
```

Salidas:
- `reports/sprint19I711/profile_boundary_audit.json`
- `reports/sprint19I711/profile_boundary_findings.csv`
