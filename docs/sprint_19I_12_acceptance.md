# Aceptación Sprint 19I.12

- usa como entrada el CSV generado en 19I.11;
- restringe la revisión a LIVA y CPEUM;
- no escribe sobre corpus, chunks, embeddings, FAISS ni catálogo;
- no deriva vigencia desde `last_reform_date`;
- no deriva vigencia automáticamente desde publicación;
- toda fecha detectada queda `candidate_only_requires_verification`;
- `promotion_ready=0` por diseño.
