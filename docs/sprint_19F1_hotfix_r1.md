# Sprint 19F.1 hotfix r1

Corrige exclusivamente el error nominal detectado por mypy en
`scripts/evaluate_runtime_retrieval.py`.

La causa era la reutilización del nombre `item` para dos tipos distintos:
`RetrievalCaseResult` y `ChunkLengthDiagnostic`. El runtime y pytest no fallaban,
pero mypy conservaba el primer tipo inferido y reportaba siete errores.

No modifica el índice FAISS, embeddings, subchunks, casos de evaluación ni
métricas.
