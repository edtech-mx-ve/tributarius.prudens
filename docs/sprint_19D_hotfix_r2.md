# Sprint 19D hotfix r2

Corrige exclusivamente la prueba de regresión del hotfix cross-volume.
`ChunkMetadata` exige `hierarchy` y `source_sha256`; la fixture de prueba ahora
los proporciona explícitamente. No modifica la lógica productiva del builder.
