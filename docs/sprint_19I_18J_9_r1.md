# Sprint 19I.18J.9 r1 — corrección

Corrige la primera entrega de J.9 sin cambiar su arquitectura.

## Cambios
- La validación de firma `%PDF-` ocurre para cualquier archivo no vacío antes de
  considerar inválido su tamaño mínimo. Esto hace que archivos HTML/texto sean
  rechazados por su formato, como exige la prueba.
- Se elimina el import no utilizado `asdict`.
- Se corrige el formato de imports y líneas mayores a 100 caracteres.

## Invariantes
- Preflight completo antes de mutar evidencia.
- No sobrescritura.
- Autoridad Cámara bajo HTTPS.
- SHA-256 y `%PDF-`.
- `public_release_allowed=False`.
