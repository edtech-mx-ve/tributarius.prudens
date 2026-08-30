# Sprint 19I.18S-r16D.0.1 — Ruff hotfix

Corrección puramente estilística del gate r16D.

## Cambios

- división de literales y expresiones largas;
- sin cambio de semántica;
- sin cambio de casos E2E;
- sin modificación del runtime ni del motor jurídico.

## Criterio de aceptación

- 4 tests del gate;
- Ruff limpio;
- mypy limpio;
- `git diff --check` limpio;
- después ejecutar E2E-01..06 contra localhost.
