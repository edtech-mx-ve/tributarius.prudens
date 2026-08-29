# Aceptación Sprint 19I.10

Criterios:

- `Settings().rag_artifact_dir` apunta a `runtime_artifacts_semantic_v2`;
- `/ready` devuelve 200 usando el valor por defecto;
- `/health` devuelve 200;
- `/` devuelve 200;
- LIVA/CPEUM/LIEPS devuelven evidencia esperada;
- no existe override de `RAG_ARTIFACT_DIR` durante el smoke;
- no se toca GitHub ni Render;
- el runtime 19F previo permanece disponible como rollback local.
