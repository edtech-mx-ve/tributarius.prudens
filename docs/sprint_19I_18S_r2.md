# Sprint 19I.18S-r2 — Hotfix de compatibilidad Render Free

## Objetivo

Eliminar `maxShutdownDelaySeconds` del Blueprint de Render porque el plan `free`
rechaza esa propiedad y bloquea la sincronización del `render.yaml`.

## Alcance

Cambio mínimo y aislado:

- se elimina únicamente `services[0].maxShutdownDelaySeconds`;
- se conserva el `buildCommand` que ejecuta
  `python -m scripts.bootstrap_runtime_release_19i18c`;
- se conserva `plan: free`;
- se conserva el SHA-256 auditado del runtime público;
- `RUNTIME_RELEASE_URL` continúa como `sync: false`;
- no se modifica lógica RAG, normativa, temporal ni de aplicación.

## Validación focalizada

```powershell
pytest -q tests/test_render_blueprint_free_tier_19s_r2.py
ruff check tests/test_render_blueprint_free_tier_19s_r2.py
mypy tests/test_render_blueprint_free_tier_19s_r2.py
python -c "import yaml; d=yaml.safe_load(open('render.yaml', encoding='utf-8')); s=d['services'][0]; assert s['plan']=='free'; assert 'maxShutdownDelaySeconds' not in s; assert 'python -m scripts.bootstrap_runtime_release_19i18c' in s['buildCommand']; print('OK: render.yaml compatible con Render Free')"
git diff --check
```

No se requiere repetir la suite integral porque este hotfix solo corrige una
propiedad del Blueprint.

## Criterios de aceptación

1. Las pruebas focalizadas pasan.
2. Ruff y mypy pasan en el test añadido.
3. `render.yaml` no contiene `maxShutdownDelaySeconds`.
4. El bootstrap de runtime permanece en `buildCommand`.
5. El SHA público permanece sin cambios.
6. Render permite `Manual sync` del Blueprint.
