# Sprint 19I.18S-r16B — Integración de frontera Unicode

## Objetivo

Conectar la normalización r16A en la frontera HTTP JSON, de manera transversal y
sin modificar el motor normativo, RAG, runtime r10 ni política temporal.

## Diseño

Se incorpora middleware ASGI que sólo procesa respuestas `application/json`.
La lógica de dominio permanece intacta. El middleware:

1. captura la respuesta;
2. sólo para JSON UTF-8 válido aplica `normalize_public_value`;
3. recalcula `Content-Length`;
4. preserva respuestas no JSON o JSON no decodificable.

Esto permite sanear `/ready`, incertidumbres, evidencia y trazabilidad con una
única frontera auditable.

## Integración requerida

Este ZIP no modifica `app/main.py` automáticamente porque primero debe
confirmarse el patrón exacto de creación de la aplicación en el repositorio
actual. Tras el gate focalizado, r16B.1 realizará una modificación mínima y
probada de `app/main.py`.

## Criterios de aceptación

- tests r16A + r16B verdes;
- Ruff y mypy verdes;
- no dependencias nuevas;
- sin cambios a Render/runtime/corpus;
- Unicode válido preservado;
- no commit/push antes de E2E local.
