# Sprint 19I.18S-r6 — Activación portable entre filesystems

## Incidente

Render validó y descargó el candidato público, pero falló al activar el
runtime en `/opt/render/project/src/deployment/runtime_artifacts_semantic_v2`.

La implementación r5 utilizaba `Path.replace()` directamente desde el
`TemporaryDirectory` hacia el checkout. En Linux/Render el temporal puede
estar en `/tmp` y el checkout en `/opt`, por lo que un rename puede fallar
entre filesystems.

## Corrección

`_replace_tree()` materializa primero el árbol validado en un directorio
`.staged` hermano del destino mediante `shutil.copytree()`. Después realiza
los renames de activación y rollback únicamente dentro del filesystem del
destino.

Se conserva:
- validación SHA-256 externa;
- contrato exacto de cinco miembros;
- validación del manifest público;
- rollback si falla la activación;
- limpieza de staging/backup.

## Validación focalizada

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

## Criterios de aceptación

- pruebas focalizadas, Ruff y mypy en verde;
- no se reconstruye el candidato público;
- Render muestra el OK del bootstrap;
- `/ready` reporta `rag_artifacts.available=true`.
