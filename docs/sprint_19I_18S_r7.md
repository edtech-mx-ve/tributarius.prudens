# Sprint 19I.18S-r7 — Corrección de tipado del test r6

Hotfix exclusivamente de prueba. Añade la anotación
`pytest.MonkeyPatch` al fixture `monkeypatch` del test de activación
cross-filesystem.

No modifica código de producción, `render.yaml`, el bootstrap, el candidato
público ni su SHA-256.

## Validación

```powershell
pytest -q `
  tests/test_runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_public_release_activation_19s_r6.py `
  tests/test_runtime_release_bootstrap_19i18c.py `
  tests/test_deployment_runtime_bootstrap_19i18c.py `
  tests/test_render_blueprint_free_tier_19s_r2.py

ruff check `
  app/services/runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_public_release_activation_19s_r6.py

mypy `
  app/services/runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_public_release_activation_19s_r6.py

git diff --check
```
