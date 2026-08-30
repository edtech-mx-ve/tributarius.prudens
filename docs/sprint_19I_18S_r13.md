# Sprint 19I.18S-r13 — Publication-audit fixture compatibility

## Objetivo

Cerrar el único bloqueo restante del CI posterior a r12 sin debilitar
`scripts.audit_github_publish` ni los controles de saneamiento de rutas del
constructor 19M.

## Cambio

El fixture de `tests/test_public_release_candidate_19i18m.py` conserva una ruta
Windows absoluta sintética bajo un directorio de pruebas para ejercitar el
saneamiento, pero deja de simular un directorio de perfil de usuario, que el
auditor de publicación rechaza deliberadamente.

No se modifica lógica de producción, reglas del auditor, integridad r11/r12,
candidato público r10 ni su SHA-256.

## Criterios de aceptación

1. `python -m scripts.audit_github_publish` termina con código 0.
2. `tests/test_public_release_candidate_19i18m.py` pasa completo.
3. Ruff permanece limpio en el alcance aplicable.
4. `python -m scripts.validate_deployment` pasa.
5. `python -m scripts.smoke_normative_jurisprudential` pasa.
6. El `pytest` integral termina con 0 fallos.
7. `git diff --check` limpio.
8. GitHub CI del commit r13 debe ser verde antes de crear tag, release o tocar Render.

## Implementación

Expandir este hotfix sobre la raíz del repositorio y ejecutar los gates locales
indicados por el Tech Lead.
