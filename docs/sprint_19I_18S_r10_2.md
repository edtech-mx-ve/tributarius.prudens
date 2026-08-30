# Sprint 19I.18S-r10.2 — gate de regresión de integridad interna

Añade un validador reutilizable e independiente del `release_manifest.json`
exterior. Comprueba SHA-256, tamaños y cardinalidad del runtime extraído.

Este parche todavía no cambia el flujo de publicación/deploy. Su objetivo es
probar localmente el gate antes de cablearlo en el cold-start/instalador.
