# Sprint 19I.18S-r14 — estabilización CPU del runtime público

## Objetivo

Evitar que la primera consulta pública materialice SentenceTransformer + Torch/CUDA en
la instancia Render Free de 512 MB. El runtime público usa un backend lexical CPU
determinista sobre el mismo corpus normativo, mantiene la política de reranking jurídico
y conserva las verificaciones SHA-256 del bundle.

## Decisiones

- `semantic` sigue siendo el backend por defecto fuera del perfil Render.
- Render Free fija `RAG_RUNTIME_BACKEND=lexical_cpu`.
- El backend lexical valida `index.faiss`, `chunks.jsonl` y `manifest.json`, aunque no
  carga FAISS ni el modelo de embeddings en memoria.
- La recuperación lexical no se presenta como semántica.
- El build instala PyTorch desde el índice CPU oficial y falla si aparecen paquetes
  `nvidia-*`, `cuda-*` o `triton`.
- Se limitan OMP/MKL/OpenBLAS/NumExpr a un hilo.
- Se mantiene el SHA inmutable del release r10:
  `18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514`.
- No se modifica el ZIP normativo r10 ni se debilita el fail-closed temporal.

## Criterios de aceptación local

1. Tests r14 en verde.
2. Ruff en verde.
3. mypy en verde para archivos modificados.
4. `python -m scripts.validate_deployment` en verde.
5. `git diff --check` limpio.
6. Auditoría de publicación en verde antes de commit/push.

## Limitaciones

El backend `lexical_cpu` es una contingencia de hosting de 512 MB. No sustituye la
evaluación semántica 19G ni autoriza a reportar métricas semánticas como si fueran
idénticas. El backend semántico continúa disponible para entornos con recursos
suficientes.

## Implementación

Desde la raíz del repositorio, expandir el ZIP r14 y ejecutar:

```powershell
python -m pytest `
  tests/test_runtime_backend_19s_r14.py `
  tests/test_cpu_runtime_gate_19s_r14.py `
  tests/test_render_cpu_profile_19s_r14.py -q

python -m ruff check `
  app/services/runtime_factory.py `
  rag/retrieval/lexical_cpu.py `
  scripts/verify_cpu_runtime_19s_r14.py `
  scripts/validate_deployment.py `
  tests/test_runtime_backend_19s_r14.py `
  tests/test_cpu_runtime_gate_19s_r14.py `
  tests/test_render_cpu_profile_19s_r14.py

python -m mypy `
  app/services/runtime_factory.py `
  rag/retrieval/lexical_cpu.py `
  scripts/verify_cpu_runtime_19s_r14.py `
  scripts/validate_deployment.py

python -m scripts.validate_deployment
git diff --check
```

Después, ejecutar la auditoría de publicación ya versionada. No hacer push ni redeploy
hasta que todos los gates locales queden limpios.
