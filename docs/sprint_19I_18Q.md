# Sprint 19I.18Q — expediente de decisión de publicación

## Objetivo

Reducir los bloqueos restantes a decisiones humanas explícitas y auditables,
sin relajar automáticamente ningún gate de publicación.

## Evidencia de licencia del modelo

El repositorio oficial del modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` identifica la
licencia como `apache-2.0`. El sprint registra esa evidencia y cierra el
hallazgo técnico de "licencia desconocida". Esto no sustituye asesoría jurídica
sobre obligaciones concretas de distribución.

## Política temporal propuesta

Para los 12 documentos sin evidencia temporal completa se mantiene:

`retrievable_but_not_promotable_as_applicable_without_authoritative_temporal_evidence`

La interfaz debe indicar estado temporal no acreditado y el motor no puede usar
esos documentos para activar tasas/reglas temporales como vigentes.

La política queda preparada, pero requiere aceptación humana expresa.

## Redistribución

Los 14 documentos normativos se mantienen como texto normativo oficial
candidato bajo LFDA art. 14 VIII, sujeto a conformidad con texto oficial y
revisión humana. No se incluye doctrina/editorial en el runtime público.

## Implementación

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\tributarius-prudens-sprint19I.18Q-patch.zip" `
  -DestinationPath "." `
  -Force

pytest tests/test_public_release_decision_dossier_19i18q.py -v

ruff check `
  app/services/public_release_decision_dossier_19i18q.py `
  scripts/validate_public_release_decision_dossier_19i18q.py `
  tests/test_public_release_decision_dossier_19i18q.py

mypy `
  app/services/public_release_decision_dossier_19i18q.py `
  scripts/validate_public_release_decision_dossier_19i18q.py

python -m scripts.validate_public_release_decision_dossier_19i18q
```

## Resultado esperado

El hallazgo de licencia del modelo queda resuelto documentalmente, pero la
publicación continúa bloqueada hasta que existan decisiones humanas explícitas
sobre la política temporal fail-closed y la redistribución normativa.
