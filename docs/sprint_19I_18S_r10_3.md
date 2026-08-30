# Sprint 19I.18S-r10.3 — cableado del gate interno y nuevo pin

Integra `validate_runtime_inner_integrity()` en el instalador público antes de
activar el runtime. Actualiza el SHA esperado del candidato a
`18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514`
en cold-start, validador de deployment y `render.yaml`.

La URL de release permanece `sync: false`: no se publica ni despliega en este
incremento. Primero se valida localmente el nuevo asset.

Criterios: pruebas focalizadas, Ruff, mypy, validate_deployment, instalación
local desde el ZIP r10 y `git diff --check`.
