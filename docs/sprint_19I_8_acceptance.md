# Aceptación Sprint 19I.8

Criterios:

- entrada exacta: `chunks_semantic_v2.jsonl`;
- 2981 padres;
- cobertura de padres 100%;
- `chunks_risk=0`;
- índice FAISS construido en directorio nuevo;
- ningún overwrite del índice 19F activo;
- benchmark 19G rerun sobre el índice semántico v2;
- `PrimaryHit@K=1.000` como mínimo;
- cualquier regresión material en `PrimaryHit@1`, `PrimaryHit@3` o `PrimaryMRR`
  debe analizarse antes de activar el nuevo runtime.
