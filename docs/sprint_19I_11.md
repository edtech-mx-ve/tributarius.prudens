# Sprint 19I.11 — auditoría de vigencia normativa v2

El runtime semántico v2 ya es el default local. LIVA y CPEUM recuperan evidencia
correcta, pero `applicable_normative_refs=0` porque el puente normativo exige
metadatos temporales verificables.

19I.11 vuelve a medir la cobertura temporal sobre los 29,326 subchunks del índice
semántico v2 y localiza líneas de la fuente normalizada con señales de vigencia,
transitorios o entrada en vigor.

Este sprint es diagnóstico. No escribe `effective_from` ni `effective_to`, y nunca
convierte `publication_date` o `last_reform_date` en fecha de vigencia.

## Implementación local

```powershell
pytest tests/test_normative_temporal_evidence_19i11.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_temporal_evidence_19i11
```

Salidas:

- `reports/sprint19I11/temporal_evidence_report.json`
- `reports/sprint19I11/temporal_document_summary.csv`
- `reports/sprint19I11/temporal_evidence_lines.csv`
- `reports/sprint19I11/integrity/*`

El siguiente incremento solo podrá enriquecer metadatos si la vigencia está
sustentada por evidencia verificable de la propia fuente.
