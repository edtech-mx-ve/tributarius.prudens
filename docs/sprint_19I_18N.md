# Sprint 19I.18N — cold-start aislado del candidato público

## Objetivo

Demostrar localmente que el ZIP producido por 19M puede ser instalado,
verificado y cargado desde una ubicación aislada sin depender de:

- `dist/public_safe_runtime_19i18k`;
- corpus PDF;
- Markdown normalizado;
- staging de construcción;
- bases de datos;
- secretos;
- pesos de modelos.

19N no autoriza publicación.

## Flujo

`ZIP 19M -> validación SHA -> seguridad ZIP -> extracción aislada ->
manifest/hashes -> chunks -> FAISS -> búsqueda vectorial de smoke ->
auditoría de suficiencia de despliegue -> reporte`

## Criterios de aceptación técnica

- SHA exacto del candidato 19M.
- No path traversal, symlinks ni entradas fuera del contrato.
- Manifest y hashes íntegros.
- 14 documentos normativos y ningún documento bloqueado.
- `chunks.jsonl` cargable.
- FAISS cargable.
- `faiss.ntotal == chunk_count`.
- Vector reconstruido y búsqueda local válidos.
- Runtime cargado exclusivamente desde la copia extraída.

## Gate de suficiencia de despliegue

El bundle 19M excluye pesos del Sentence Transformer por diseño. Por ello
19N separa dos conceptos:

- `cold_start_acceptance=True`: el artefacto de runtime FAISS/chunks es
  íntegro y arrancable en aislamiento.
- `deployment_sufficiency_acceptance=False`: todavía no se ha demostrado que
  un host limpio pueda obtener/cargar el modelo de embeddings requerido para
  transformar consultas de texto.

Esto evita declarar autosuficiencia semántica sin evidencia.

## Implementación

Desde la raíz del repositorio:

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\tributarius-prudens-sprint19I.18N-patch.zip" `
  -DestinationPath "." `
  -Force

pytest tests/test_public_release_cold_start_19i18n.py -v

ruff check `
  app/services/public_release_cold_start_19i18n.py `
  scripts/validate_public_release_cold_start_19i18n.py `
  tests/test_public_release_cold_start_19i18n.py

mypy app/services/public_release_cold_start_19i18n.py `
  scripts/validate_public_release_cold_start_19i18n.py

python -m scripts.validate_public_release_cold_start_19i18n
```

Salida:

`dist/public_release_cold_start_19i18n/cold_start_acceptance.json`

No ejecutar Git/Render después de 19N.
