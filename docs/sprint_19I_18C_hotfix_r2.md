# Sprint 19I.18C hotfix r2

Corrige exclusivamente el orden alfabético de los símbolos importados desde
`app.services.runtime_release_installer` en
`scripts/bootstrap_runtime_release_19i18c.py`.

Ruff/I001 exige:

```python
from app.services.runtime_release_installer import (
    RuntimeReleaseInstallError,
    install_runtime_release,
)
```

No cambia lógica, `render.yaml`, SHA-256, variables de entorno ni políticas
fail-closed.

## Validación local

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.validate_deployment
python -m scripts.audit_sprint19_local_acceptance_19i17
python -m scripts.smoke_temporal_runtime_e2e_19i16
```
