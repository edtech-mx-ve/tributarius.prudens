# Aceptación Sprint 19I.18I

- cubre exactamente los 14 documentos normativos candidatos;
- resuelve `source_filename` contra el corpus local;
- calcula SHA-256 en streaming, sin cargar PDFs completos en memoria;
- exige un único `source_sha256` coherente por documento;
- cualquier PDF faltante o hash distinto queda bloqueado;
- genera `reports/sprint19I18I/runtime_source_bridge.json`;
- no modifica chunks, PDFs, FAISS ni políticas de redistribución;
- `public_release_allowed` permanece `False`;
- Ruff, mypy y pytest completos deben permanecer limpios.
