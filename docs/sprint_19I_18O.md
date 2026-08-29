# Sprint 19I.18O — cierre de dependencia externa de embeddings

## Objetivo

Cerrar el único hallazgo técnico abierto por 19N:

`deployment_sufficiency_acceptance=False`

El candidato 19M no incluye pesos del Sentence Transformer. 19O demuestra,
sin APIs comerciales, claves ni tarjeta, que el modelo exacto requerido por
el runtime puede:

1. resolverse desde los metadatos del runtime;
2. descargarse en una cache nueva y aislada;
3. recargarse en modo offline desde esa cache;
4. vectorizar una consulta fiscal;
5. producir la dimensión exacta esperada por FAISS;
6. recuperar resultados reales del índice del candidato.

## Alcance

La cache de modelo es un artefacto local de build bajo `dist/`; no se añade al
candidato público ni a Git.

19O no resuelve el gate jurídico/temporal y no autoriza publicación.

## Implementación

Desde la raíz:

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\tributarius-prudens-sprint19I.18O-patch.zip" `
  -DestinationPath "." `
  -Force

pytest tests/test_public_release_deployment_dependency_19i18o.py -v

ruff check `
  app/services/public_release_deployment_dependency_19i18o.py `
  scripts/validate_public_release_deployment_dependency_19i18o.py `
  tests/test_public_release_deployment_dependency_19i18o.py

mypy `
  app/services/public_release_deployment_dependency_19i18o.py `
  scripts/validate_public_release_deployment_dependency_19i18o.py

python -m scripts.validate_public_release_deployment_dependency_19i18o
```

La prueba funcional requiere acceso normal a Internet para descargar una vez el
modelo público desde su repositorio. No usa token ni API de pago.

## Aceptación esperada

- `fresh_unauthenticated_model_fetch_passed=True`
- `offline_model_reload_passed=True`
- `semantic_query_embedding_cold_start_proven=True`
- `embedding_dimension=384`
- `faiss_dimension=384`
- `deployment_sufficiency_acceptance=True`

Permanecen falsos los gates de publicación, GitHub y Render.
