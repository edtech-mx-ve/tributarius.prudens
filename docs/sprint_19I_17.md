# Sprint 19I.17 — auditoría integral de aceptación local

Consolida los invariantes técnicos críticos del Sprint 19 antes de cualquier
operación remota.

## Gate

La auditoría valida:

- corpus semántico promovido: estado, 2981 padres, 16 documentos y SHA-256 real;
- runtime semántico v2: 29326 subchunks, dimensión 384, modelo esperado y hashes
  reales de `index.faiss` y `chunks.jsonl`;
- runtime por defecto: `deployment/runtime_artifacts_semantic_v2`;
- registro temporal: LIVA/CPEUM continúan bloqueados con
  `unknown_fail_closed`;
- ninguna entrada temporal 19I.14 contiene `effective_from`/`effective_to` ni
  autorización documental automática.

La auditoría genera únicamente:
`reports/sprint19I17/local_acceptance_audit.json`.

## Implementación local

```powershell
pytest tests/test_sprint19_local_acceptance_audit_19i17.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_sprint19_local_acceptance_19i17
python -m scripts.smoke_temporal_runtime_e2e_19i16
python -m scripts.validate_deployment
```

No hacer `git push` ni desplegar en Render hasta que los tres comandos finales
terminen correctamente y el cierre local sea aceptado.
