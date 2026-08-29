# Sprint 19I.18C hotfix r1

Corrige exclusivamente el bloque de imports de
`scripts/bootstrap_runtime_release_19i18c.py` para satisfacer Ruff/I001 y elimina
la constante `_REQUIRED_ENV`, que no participaba en la ejecución.

No cambia la lógica del bootstrap, `render.yaml`, la URL externa, el SHA-256
fijado, las políticas fail-closed ni el comportamiento de despliegue.

## Validación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.validate_deployment
python -m scripts.audit_sprint19_local_acceptance_19i17
python -m scripts.smoke_temporal_runtime_e2e_19i16
```
