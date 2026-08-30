# Sprint 19I.18S-r11 — prevención de recurrencia y pin operativo

## Objetivo
Cerrar el defecto de construcción que permitió que la sanitización de
`chunks.jsonl` dejara obsoleto el SHA interno del runtime.

## Cambios
- El constructor 19M recalcula `chunks_sha256`, `chunks_bytes`,
  `index_sha256` e `index_bytes` después de sanitizar.
- Ejecuta el gate de integridad interna antes de calcular los digests
  exteriores y construir `release_manifest.json`.
- La auditoría de staging y el test de Render usan el candidato operativo
  reparado `18ac85d3...`.
- Los pins históricos de 19O/19P no se reescriben.
- No se incluye ningún artefacto de `dist/`.

## Criterios de aceptación
Pruebas focalizadas, Ruff, mypy, validación de deployment, regresión de
integridad, `git diff --check` y auditoría de staging antes de commit.
