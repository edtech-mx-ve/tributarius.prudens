# Sprint 19H hotfix r1

## Problema observado

El smoke end-to-end de Sprint 19H reveló que el score compuesto del reranker
jurídico 19G puede superar 1.0 (ejemplo real: 1.0243). El contrato
`EvidenceReference.score` exige valores en el intervalo `[0, 1]`, por lo que
Pydantic rechazaba la evidencia durante la construcción de trazabilidad.

## Corrección

- El score compuesto crudo sigue utilizándose para ordenar candidatos.
- `LegalScoreTrace.final_score` conserva el score crudo para trazabilidad.
- `RetrievalHit.score`, que cruza hacia contratos downstream, se limita de forma
  determinista al intervalo `[0, 1]`.
- Se rechazan scores no finitos.
- Se añade una prueba de regresión que reproduce un score compuesto mayor a 1.

No se modifica FAISS, embeddings, subchunks, benchmark ni política de
priorización jurídica.
