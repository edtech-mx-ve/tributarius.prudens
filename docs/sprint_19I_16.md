# Sprint 19I.16 — smoke E2E del guard temporal

Valida el comportamiento integral del runtime después de 19I.15.

## Invariantes

1. `/ready`, `/health` y `/` deben responder correctamente.
2. LIVA debe seguir apareciendo en la evidencia recuperada.
3. CPEUM debe seguir apareciendo en la evidencia recuperada.
4. LIVA y CPEUM deben producir cero `applicable_normative_refs` mientras el
   registro temporal los marque `unknown_fail_closed`.
5. Un documento no bloqueado (LIEPS) debe seguir recuperándose; este smoke no
   fuerza un número de referencias normativas para LIEPS porque eso depende de
   su propia evidencia temporal y consistencia de unidad.
6. No se modifica FAISS, corpus ni metadatos de chunks.

## Implementación local

```powershell
pytest tests/test_temporal_runtime_e2e_contract_19i16.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.smoke_temporal_runtime_e2e_19i16
```

No realizar push ni despliegue hasta cerrar todas las validaciones locales del
Sprint 19.
