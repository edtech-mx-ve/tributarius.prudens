# Sprint 19I.12 — revisión temporal prioritaria LIVA/CPEUM

19I.11 confirmó:

- runtime semántico v2: 29,326 subchunks;
- normativa: 26,101;
- cobertura temporal conocida: 9,330;
- temporal desconocida: 16,771;
- temporal inválida: 0;
- LIVA: 1,188/1,188 desconocidos;
- CPEUM: 3,613/3,613 desconocidos.

19I.12 no modifica metadatos. Filtra las líneas de evidencia temporal obtenidas
en 19I.11 para LIVA y CPEUM y las clasifica por fuerza semántica:

1. entrada en vigor explícita;
2. efectos a partir de fecha;
3. contexto transitorio;
4. referencia de publicación;
5. vigencia genérica;
6. no clasificada.

Las fechas textuales detectadas se exportan como candidatas, nunca como
`effective_from`/`effective_to`.

## Implementación local

```powershell
pytest tests/test_normative_temporal_priority_review_19i12.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.review_priority_temporal_evidence_19i12
```

Salidas:

- `reports/sprint19I12/priority_temporal_review.json`
- `reports/sprint19I12/priority_temporal_candidates.csv`

El siguiente sprint solo podrá promover una fecha si existe evidencia inequívoca
y verificable de la propia fuente normativa.
