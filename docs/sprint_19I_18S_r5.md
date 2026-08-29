# Sprint 19I.18S-r5

Hotfix focalizado sobre r4.

Corrige los tres hallazgos de aceptación:
- elimina el import `os` no utilizado;
- hace explícito el acceso a `RuntimeReleaseInstallError` para mypy;
- actualiza el validador de despliegue del SHA legacy privado al SHA auditado
  del candidato público 19M.

No modifica el ZIP público, no cambia su SHA y no amplía el contrato de
archivos permitidos.

## Implementación y validación

```powershell
pytest -q `
  tests/test_runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_release_bootstrap_19i18c.py `
  tests/test_deployment_runtime_bootstrap_19i18c.py `
  tests/test_render_blueprint_free_tier_19s_r2.py

ruff check `
  app/services/runtime_public_release_installer_19s_r4.py `
  scripts/bootstrap_runtime_release_19i18c.py `
  scripts/validate_deployment.py `
  tests/test_runtime_public_release_installer_19s_r4.py

mypy `
  app/services/runtime_public_release_installer_19s_r4.py `
  scripts/bootstrap_runtime_release_19i18c.py `
  scripts/validate_deployment.py

git diff --check
```
