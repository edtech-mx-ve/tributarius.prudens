# Sprint 19I.18S-r16B.1 — Integración FastAPI real

## Cambio

Se registra `PublicUnicodeNormalizationMiddleware` en `app/main.py`, después de
los middlewares de seguridad ya existentes. El cambio se limita a la frontera
HTTP JSON y no altera el dominio, el motor normativo, RAG ni el runtime.

Se añaden regresiones sobre la aplicación FastAPI real:

- `/ready` debe emitir JSON UTF-8 explícito y sin marcadores conocidos de
  mojibake;
- `/health` debe conservar su contrato.

## Base verificada

La integración se preparó contra `app/main.py` del commit base
`8aa5f39504601593b3185bd11f93f1be1af975d9`.

## Criterios de aceptación

- gate acumulado r16A+r16B+r16B.1 verde;
- Ruff/mypy verdes;
- `git diff --check` limpio;
- sin cambios en Render, runtime r10, corpus, FAISS o política temporal;
- todavía sin commit/push/deploy.
