# Sprint 19I.7.4 — identidad de fronteras legales

19I.7.3 demostró que las 135 líneas fuente sí satisfacen el parser actual.
La aparente “absorción” de 19I.7.2 se basaba en cambio de `text_sha256`, no en
ausencia de la frontera. Este incremento verifica la identidad estructural por:

`canonical_id + unit_type + unit_label`

Así diferencia una frontera realmente perdida de un artículo preservado cuyo
contenido creció al eliminarse falsas fronteras internas posteriores.

## Implementación local

```powershell
pytest tests/test_legal_boundary_identity_audit_19i74.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_boundary_identity_19i74
```

No modifica 19C, candidato 19I.7, embeddings ni FAISS.
