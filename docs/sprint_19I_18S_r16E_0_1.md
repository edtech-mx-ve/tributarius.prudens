# Sprint 19I.18S-r16E.0.1 — mypy hotfix

Corrección focalizada del smoke HTTP r16E.

## Causa

`json.loads()` retorna `Any` para mypy y el helper `_post()` declaraba
`dict[str, Any]`, activando `no-any-return`.

## Corrección

- valida que el JSON decodificado sea un objeto;
- aplica `cast(dict[str, Any], decoded)` después de la validación;
- no cambia el runtime, middleware, evidencia ni decisiones jurídicas.

## Criterio de aceptación

- tests r16E: 5 PASS;
- Ruff limpio;
- mypy limpio;
- `git diff --check` limpio.
