# Sprint 19I.16 hotfix r2

Corrige el parser del smoke E2E para respetar el contrato real de
`WebConsultationResponse`.

La API devuelve un sobre con:

```json
{
  "status": "ready",
  "message": "...",
  "result": {
    "evidence": [],
    "applicable_normative_refs": []
  }
}
```

El smoke anterior intentaba leer `evidence` directamente en el nivel superior,
por eso falló con `evidence no es una lista JSON`.

## Alcance

- valida `status == "ready"`;
- extrae `result`;
- lee `evidence` y `applicable_normative_refs` desde `result`;
- mantiene la política fail-closed;
- no modifica runtime, corpus, FAISS, metadatos ni reglas normativas.

## Implementación local

```powershell
pytest tests/test_temporal_runtime_e2e_contract_19i16.py -v
pytest tests/test_temporal_runtime_e2e_smoke_parser_19i16.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_e2e_19i16
```
