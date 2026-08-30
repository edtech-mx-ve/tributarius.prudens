# Sprint 19I.18S-r8 — Observabilidad segura del RuntimeBuildError

## Objetivo

Hacer visible en logs la causa técnica exacta que provoca la degradación
`not_configured` del servicio web, sin alterar la política fail-safe.

## Cambio

`app/web/dependencies.py` conserva el comportamiento actual:

- si `build_runtime_components()` funciona, conecta el runner real;
- si lanza `RuntimeBuildError`, devuelve `WebConsultationService()` degradado.

Ahora el `WARNING` incluye exclusivamente:

- tipo de excepción;
- mensaje de `RuntimeBuildError`.

No registra la consulta del usuario, headers, cuerpo HTTP, secretos ni variables
de entorno.

## Gate local

```powershell
pytest -q `
  tests/test_web_runtime_observability_19s_r8.py `
  tests/test_runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_public_release_activation_19s_r6.py `
  tests/test_runtime_release_bootstrap_19i18c.py `
  tests/test_deployment_runtime_bootstrap_19i18c.py `
  tests/test_render_blueprint_free_tier_19s_r2.py

ruff check `
  app/web/dependencies.py `
  tests/test_web_runtime_observability_19s_r8.py

mypy `
  app/web/dependencies.py `
  tests/test_web_runtime_observability_19s_r8.py

git diff --check
```

## Criterios de aceptación

- pruebas focalizadas en verde;
- Ruff limpio;
- mypy limpio;
- diff limpio;
- el servicio sigue degradando de forma segura ante RuntimeBuildError;
- un deployment diagnóstico muestra `cause_type` y `cause` en Render.
