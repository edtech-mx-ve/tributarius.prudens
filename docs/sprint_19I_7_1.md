# Sprint 19I.7.1 — auditoría causal del delta semántico

El candidato 19I.7 redujo 3174 chunks a 2981. Esa reducción no se promueve sin
explicar causalmente qué unidades desaparecieron, cuáles fueron absorbidas por
un padre correcto y cuáles podrían ser artículos legítimos perdidos.

La auditoría compara `text_sha256`, documento y contenido para clasificar
unidades retiradas y nuevas. Las pérdidas de artículos numéricos legítimos se
marcan `requires_review`; las fronteras con etiquetas de referencia como
`Artículo 166 de` se identifican por separado.

## Implementación

```powershell
pytest tests/test_semantic_delta_audit_19i71.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_semantic_delta_19i71
```

Salidas:

- `reports/sprint19I71/semantic_delta_audit.json`
- `reports/sprint19I71/removed_units.csv`
- `reports/sprint19I71/added_units.csv`

Este incremento es diagnóstico: no modifica 19C, el candidato 19I.7 ni FAISS.
