# Aceptación Sprint 19I.7.8

Criterios:
- `total_residuals=25`;
- los 4 `missing_reference_like_boundary` deben quedar preservados o requerir
  revisión explícita;
- ningún residual se elimina silenciosamente;
- cualquier caso no seguro conserva estado `requires_review`;
- no se promueve el candidato hasta revisar los residuos restantes.
