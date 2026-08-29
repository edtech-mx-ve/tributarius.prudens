# Sprint 19I.18J.11 r3 — resolución robusta del PDF local

El reporte real J.18I no expuso una ruta/campo SHA utilizable por J.11 para
`lfdc`. r3 endurece la resolución sin mutar el corpus:

1. busca recursivamente metadatos por `document_id`;
2. acepta más nombres de campo SHA;
3. puede usar `local_sha256` de J.7;
4. si no hay SHA, usa alias canónicos de archivo dentro de `--local-corpus-dir`;
5. falla si hay ambigüedad o si el candidato contradice un SHA registrado.

Alias incorporados:

- `LFDC.pdf`
- `Reg_LIVA_250914.pdf`

No se altera evidencia, PDF local, Markdown, chunks, FAISS ni políticas.
