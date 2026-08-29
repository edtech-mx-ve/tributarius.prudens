# Sprint 19I.18A — empaquetado local del runtime para release

El cierre local 19I.17 confirmó que la aplicación funciona con el runtime
semántico v2. El siguiente problema de despliegue es que ese runtime es un
artefacto generado y no debe incorporarse directamente al historial Git.

Este incremento crea un ZIP determinista bajo `dist/`, ya ignorado por Git, con:

- `deployment/runtime_artifacts_semantic_v2/index.faiss`
- `deployment/runtime_artifacts_semantic_v2/chunks.jsonl`
- `deployment/runtime_artifacts_semantic_v2/manifest.json`
- `knowledge/temporal/temporal_provenance_registry.json`
- `release_manifest.json`

Antes de empaquetar se validan los SHA-256 declarados por el manifiesto del
índice. Después se vuelve a abrir el ZIP y se verifican todos los hashes
internos.

## Implementación local

```powershell
Expand-Archive `
  -Path "tributarius-prudens-sprint19I.18A-patch.zip" `
  -DestinationPath "." `
  -Force

pytest tests/test_runtime_release_bundle_19i18a.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.package_runtime_release_19i18a
```

Conservar la salida `bundle_sha256` y `bundle_size_bytes`: se utilizarán en el
siguiente incremento para fijar el bootstrap de despliegue.

No ejecutar `git push`, no crear todavía un GitHub Release y no desplegar en
Render.
