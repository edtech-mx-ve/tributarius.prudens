# Sprint 19I.18S-r10.3.2 — fixture de candidato coherente

Actualiza exclusivamente la fixture del instalador público para construir un
`runtime/manifest.json` coherente con los bytes sintéticos de `chunks.jsonl` e
`index.faiss`.

No relaja validaciones productivas. El gate interno sigue siendo fail-closed.
La prueba de instalación ahora representa un candidato válido bajo el contrato
r10.
