# Sprint 19I.18L-r1 — hotfix de calidad estática

Corrección de formato y estilo detectada por Ruff en el primer parche 19L.

No cambia la semántica del gate:

- SHA público 19K: `7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0`
- parents: 2962
- 14 documentos normativos
- procedencia oficial diferenciada
- LFDC y Reg LIVA conservan la cadena J12.1 -> J12.4 -> K
- temporalidad conocida solo para LIF 2026 y RMF 2026
- las otras 12 fuentes permanecen fail-closed
- no existe promoción automática de redistribución
- Git, GitHub Release y Render permanecen bloqueados.

El hotfix únicamente refactoriza las tres unidades nuevas para cumplir Ruff.
