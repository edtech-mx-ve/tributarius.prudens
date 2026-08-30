# Sprint 19I.18S-r9 — Diagnóstico de causa raíz del runtime RAG

## Objetivo

Conservar en `RuntimeBuildError` el tipo y mensaje de la excepción técnica
controlada (`EmbeddingError`, `RetrievalError` o `RuleLoadError`) que impide
inicializar el runtime RAG.

La frontera de abstracción no cambia: la capa web continúa recibiendo
`RuntimeBuildError` y manteniendo degradación segura.

## Seguridad

El diagnóstico se deriva exclusivamente de la excepción interna capturada.
No se agregan consultas de usuario, headers, cuerpos HTTP, variables de
entorno ni secretos al log.

## Gate local

```powershell
pytest -q `
  tests/test_runtime_factory_observability_19s_r9.py `
  tests/test_web_runtime_observability_19s_r8.py `
  tests/test_runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_public_release_activation_19s_r6.py `
  tests/test_runtime_release_bootstrap_19i18c.py `
  tests/test_deployment_runtime_bootstrap_19i18c.py `
  tests/test_render_blueprint_free_tier_19s_r2.py

ruff check `
  app/services/runtime_factory.py `
  tests/test_runtime_factory_observability_19s_r9.py

mypy `
  app/services/runtime_factory.py `
  tests/test_runtime_factory_observability_19s_r9.py

git diff --check
```
