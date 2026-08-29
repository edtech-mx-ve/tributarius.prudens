# Sprint 19I.18S — publicación controlada y staging seguro

## Objetivo

Cerrar la transición desde la aceptación humana 19I.18R hacia un commit público
controlado, sin versionar corpus privado, chunks, índices, bases de datos, cachés de
modelos ni reportes generados.

## Candidato público fijado

- ZIP público auditado SHA-256:
  `4766b49014c5f40aa509b325ddb7268ca7032348559937d2ebae74b0dcefe360`
- Canonical normativo público:
  `7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0`
- Runtime público: solo normativa.
- Doctrina/editorial: excluida.
- Política temporal: fail-closed.

## Cambios

1. `render.yaml` fija el SHA del candidato público aprobado.
2. `.gitignore` excluye variantes de runtime, retrieval chunks, reportes y el
   archivo local de inspección.
3. El auditor 19I.18S rechaza staging de rutas generadas o privadas.
4. El registro temporal debe estar tracked o staged antes del commit.

## Criterio de aceptación

`python -m scripts.audit_publication_staging_19i18s` debe terminar con:

```text
DECISION=SAFE_TO_COMMIT
```

La autorización representa una decisión humana de publicación bajo el alcance
auditado y la política temporal fail-closed; no constituye una determinación jurídica
automática realizada por el software.
