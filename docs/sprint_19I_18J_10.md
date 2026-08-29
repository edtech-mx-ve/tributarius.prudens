# Sprint 19I.18J.10 — reconciliación integral de procedencia oficial

## Objetivo

Consolidar en un único gate local y fail-closed cuatro dimensiones que no deben
confundirse:

1. puente criptográfico runtime → PDF local;
2. conformidad técnica del contenido runtime;
3. procedencia binaria oficial Cámara/DOF;
4. redistribución y vigencia temporal.

La procedencia exacta **no** concede por sí sola derecho de redistribución ni
prueba vigencia jurídica.

## Cobertura

Normativa:

- 13 documentos de Cámara de Diputados verificados mediante J.7;
- RMF 2026 verificada contra DOF por la auditoría J;
- puente local J.18I;
- conformidad J.18G;
- base legal J.18J.4;
- política de publicación J.18E;
- registro temporal.

UNAM y PRODECON permanecen en revisión separada.

## Implementación

Antes de J.10 deben completarse:

```powershell
python -m scripts.import_browser_official_evidence_batch_19i18j9 `
  --downloads-dir "$env:USERPROFILE\Downloads"

python -m scripts.audit_browser_official_evidence_19i18j7
```

Luego:

```powershell
python -m scripts.reconcile_official_provenance_19i18j10
```

Reporte:

`reports/sprint19I18J10/runtime_official_provenance_reconciliation.json`

## Criterio técnico esperado

Si los 13 documentos de Cámara son idénticos al corpus y RMF ya mantiene su
verificación DOF:

- `official_provenance_exact_normative_count=14`
- `official_provenance_complete_for_normative_corpus=True`

Aun así, mientras no se resuelvan redistribución y vigencia:

- `public_release_allowed=False`
- `git_push_allowed=False`
- `github_release_allowed=False`
- `render_deploy_allowed=False`

## Limitaciones

Este sprint no efectúa asesoramiento legal, no interpreta licencias, no crea
fechas de vigencia y no publica artefactos.
