# Sprint 19G hotfix r2

Corrige exactamente los dos problemas observados en validación local:

1. orden/formato del bloque de imports reportado por Ruff;
2. reutilización de variables `before` y `after` con tipos `float` y
   `RetrievalCaseResult`, reportada por mypy.

No modifica FAISS, embeddings, subchunks, política jurídica, benchmark,
métricas ni criterios de aceptación.
