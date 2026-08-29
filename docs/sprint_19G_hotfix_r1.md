# Sprint 19G hotfix r1

Corrige únicamente un conflicto de inferencia de tipos detectado por mypy en
`scripts/compare_runtime_retrieval_19g.py`.

La causa era la reutilización de nombres de variables (`before` y `after`) para
valores `float` y luego para objetos `RetrievalCaseResult`. Python y pytest no
fallaban, pero mypy mantenía el tipo inferido previo.

No modifica política jurídica, FAISS, embeddings, subchunks, benchmark ni
criterios de aceptación.
