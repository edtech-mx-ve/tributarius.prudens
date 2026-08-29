# Aceptación Sprint 19I.18J

- usa el bridge verificado de 19I.18I;
- cubre exactamente los 14 documentos normativos;
- descarga solo por HTTPS desde hosts oficiales permitidos;
- revalida host después de redirects;
- valida firma PDF, timeout y tamaño máximo;
- compara SHA-256 remoto vs. SHA-256 local;
- clasifica match exacto como procedencia oficial verificada;
- bloquea hash distinto, error de descarga o falta de candidato;
- no promueve todavía derechos de redistribución;
- no modifica chunks, PDFs, índice FAISS ni release;
- Ruff, mypy y pytest completos permanecen limpios.
