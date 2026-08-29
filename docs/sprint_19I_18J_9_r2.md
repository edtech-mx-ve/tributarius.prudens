# Sprint 19I.18J.9 r2 — autodetección segura del registro oficial

## Incidencia
La entrega anterior usó como valor predeterminado un nombre de archivo de
registro que no existe en el repositorio real.

## Corrección
El CLI ya no adivina un nombre. Busca en `app/resources` un único JSON que:

1. contenga los 13 documentos de Cámara requeridos;
2. contenga para cada documento una URL HTTPS de `www.diputados.gob.mx`;
3. tenga `official` y `source` en el nombre.

Si no existe ninguno o existen varios compatibles, falla cerrado y solicita
`--registry` explícito.

## Seguridad
No se relaja ninguna validación del lote ni se habilita publicación.
`public_release_allowed=False` se mantiene.
