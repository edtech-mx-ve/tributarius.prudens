# Aceptación — Sprint 19I.18J.7

Criterios:

1. Pruebas focalizadas verdes.
2. Ruff limpio.
3. mypy limpio.
4. Suite integral verde.
5. Auditoría real del CFF ejecutada contra:
   - `dist/browser_official_evidence_19i18j6/evidence_manifest.json`
   - `reports/sprint19I18I/runtime_source_bridge.json`
6. Si los SHA-256 son idénticos, CFF queda con estado
   `exact_binary_official_source_verified`.
7. Si difieren, el sistema queda fail-closed y no se interpreta la diferencia
   como corrupción ni como invalidez jurídica.
8. `public_release_allowed=false` en todos los casos.
