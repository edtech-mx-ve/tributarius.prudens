python -m pytest `
  tests/test_public_response_quality_19s_r16.py `
  -q

python -m ruff check `
  app/services/public_response_quality_19s_r16.py `
  scripts/preflight_public_response_19s_r16.py `
  tests/test_public_response_quality_19s_r16.py

python -m mypy `
  app/services/public_response_quality_19s_r16.py `
  scripts/preflight_public_response_19s_r16.py

git diff --check# Sprint 19I.18S-r16 — Public Response Quality & Trace Integrity

## Objetivo

Cerrar la deuda de calidad de respuesta observada después de r15 sin modificar
el runtime público r10, su SHA, el backend `lexical_cpu`, la política temporal ni
el alcance `normative_only`.

## Incremento r16A

Este incremento introduce funciones puras y probadas para:

- reparación conservadora de mojibake UTF-8/Latin-1;
- normalización recursiva de valores públicos;
- deduplicación estable de evidencia por `ref_id`;
- explicación determinista del motivo de revisión normativa;
- gate CLI sobre JSON capturado.

No conecta todavía estas funciones a rutas o al orquestador. Esa integración se
realiza sólo después de verificar compatibilidad contra el commit base
`8aa5f39504601593b3185bd11f93f1be1af975d9`.

## Criterios de aceptación r16A

1. Tests focalizados verdes.
2. Ruff verde.
3. mypy verde.
4. `git diff --check` limpio.
5. Ningún cambio en `render.yaml`, runtime r10, FAISS, chunks o política temporal.
6. Sin dependencia nueva.
7. Sin Llama activado todavía.

## Limitaciones

La utilidad de normalización no sustituye la corrección de la causa de encoding.
r16B deberá conectar el saneamiento en la frontera pública y alinear la traza
normativa con el `requires_human_review` global, con regresiones E2E.
