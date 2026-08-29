# Sprint 19I.18R — decisión humana y gate final de autorización

## Decisión registrada

El propietario del proyecto declaró expresamente:

> A. Acepto ambas decisiones.

Se registra como aceptación de:

1. política temporal fail-closed para los documentos cuya vigencia no está
   acreditada con evidencia temporal autoritativa;
2. redistribución del runtime normativo público, limitado al contenido
   normativo auditado y sin doctrina/editorial bloqueada.

## Alcance

La autorización no elimina la incertidumbre temporal. Los documentos guardados
por la política temporal siguen siendo recuperables pero no promovibles como
aplicables ni pueden activar reglas/tasas temporales sin evidencia.

## Criterios de aceptación

- expediente 19Q válido;
- decisión humana explícita, fechada y atribuible;
- ambas decisiones `APPROVED`;
- doctrina/editorial excluida;
- condiciones fail-closed preservadas.

## Implementación

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\tributarius-prudens-sprint19I.18R-patch.zip" `
  -DestinationPath "." `
  -Force

pytest tests/test_public_release_human_gate_19i18r.py -v

ruff check `
  app/services/public_release_human_gate_19i18r.py `
  scripts/validate_public_release_human_gate_19i18r.py `
  tests/test_public_release_human_gate_19i18r.py

mypy `
  app/services/public_release_human_gate_19i18r.py `
  scripts/validate_public_release_human_gate_19i18r.py

python -m scripts.validate_public_release_human_gate_19i18r
```

## Después de 19R

No repetir la suite integral. Si el gate queda aprobado, el siguiente paso es
publicación controlada y smoke post-deploy sobre el artefacto ya auditado.
