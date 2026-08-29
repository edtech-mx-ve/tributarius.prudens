# Sprint 19I.18S-r4 — Compatibilidad del bootstrap con candidato público 19M

## Incidente observado

Render ejecutó el bootstrap y rechazó el asset público con:

`Archivo no permitido en bundle: 'release_metadata.json'`.

La causa es una incompatibilidad de contratos: el instalador 19B fue diseñado
para el bundle privado/legacy, mientras que el candidato público 19M usa el
contrato auditado `runtime/* + release_metadata.json + release_manifest.json`.

## Corrección

Se añade un instalador específico para el candidato público. No se relaja el
instalador legacy.

El nuevo instalador:

- exige SHA-256 externo exacto;
- acepta solo los cinco miembros exactos del candidato público;
- reutiliza la validación fail-closed de 19N;
- valida `release_metadata.json` y el manifest interno;
- instala `runtime/{index.faiss,chunks.jsonl,manifest.json}` en
  `deployment/runtime_artifacts_semantic_v2`;
- exige que el registro temporal versionado ya exista en el checkout;
- conserva sustitución transaccional del runtime;
- rechaza miembros extra y rutas fuera del contrato.

El bootstrap 19C mantiene el mismo nombre de función interno para preservar
compatibilidad con las pruebas existentes.

## Validación focalizada

```powershell
pytest -q `
  tests/test_runtime_public_release_installer_19s_r4.py `
  tests/test_runtime_release_bootstrap_19i18c.py `
  tests/test_deployment_runtime_bootstrap_19i18c.py

ruff check `
  app/services/runtime_public_release_installer_19s_r4.py `
  scripts/bootstrap_runtime_release_19i18c.py `
  tests/test_runtime_public_release_installer_19s_r4.py

mypy `
  app/services/runtime_public_release_installer_19s_r4.py `
  scripts/bootstrap_runtime_release_19i18c.py

git diff --check
```

No se repite la suite integral: el cambio está limitado al adaptador de
instalación del release público y al bootstrap de despliegue.

## Criterios de aceptación

1. Pruebas focalizadas en verde.
2. Ruff y mypy en verde.
3. El asset público conserva SHA-256
   `4766b49014c5f40aa509b325ddb7268ca7032348559937d2ebae74b0dcefe360`.
4. Render muestra el mensaje `runtime de despliegue instalado y verificado`.
5. `/ready` reporta `rag_artifacts.available=true`.
