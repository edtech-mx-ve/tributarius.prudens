# Sprint 19I.18J.7 — Puente criptográfico evidencia navegador → PDF local

## Objetivo

Comparar la evidencia PDF descargada manualmente desde una URL oficial registrada
por el flujo 19I.18J.6 contra el SHA-256 del PDF local previamente verificado por
el puente 19I.18I.

## Invariantes de seguridad

- Solo se aceptan documentos existentes en el registro oficial.
- La URL declarada por J.6 debe coincidir exactamente con una URL candidata
  registrada y usar HTTPS en un host permitido.
- El archivo importado se vuelve a hashear y su tamaño debe coincidir con el
  manifest J.6.
- El bridge 19I.18I debe marcar `bridge_verified=true`.
- Coincidencia exacta SHA-256 produce
  `exact_binary_official_source_verified`.
- Diferencia binaria produce `official_binary_differs_from_local_pdf`.
- Evidencia alterada produce `evidence_integrity_failed`.
- El sprint nunca cambia `public_release_allowed` a `true`.
- No infiere licencia, derechos de redistribución, vigencia temporal ni
  completitud jurídica.

## Salida

`reports/sprint19I18J7/browser_official_evidence_bridge.json`
