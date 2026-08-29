# Sprint 19I.18J.9 r3 — reconciliación de plan J.8 con evidencia ya importada

## Incidencia
J.8 fue generado antes de importar CPEUM. Por ello todavía lo marca como
`pending_browser_download`, mientras el manifest J.6 ya contiene evidencia
válida para CPEUM.

## Corrección
J.9 se vuelve idempotente frente a un plan desactualizado:

- si un documento pendiente ya está en el manifest, no se sobrescribe;
- antes de omitirlo, se revalida URL oficial, existencia, `%PDF-`, tamaño y
  SHA-256 contra el manifest;
- si la evidencia existente fue alterada, falla cerrado;
- los demás documentos pendientes continúan exigiendo su PDF en Downloads.

Esto preserva la evidencia CFF/CPEUM y evita regenerar J.8 solo por cambio de
estado.

## Política
No cambia vigencia temporal, derechos de redistribución ni autorización de
publicación. `public_release_allowed=False`.
