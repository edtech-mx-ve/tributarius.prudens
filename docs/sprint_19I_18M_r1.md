# Sprint 19I.18M-r1 — sanitización determinista de rutas privadas

## Motivo

La primera ejecución funcional de 19M detectó correctamente rutas locales
absolutas en `chunks.jsonl` y `manifest.json`.

Esas rutas son metadatos de construcción del runtime local 19K. No deben
aparecer en un bundle público, pero tampoco justifican modificar o reconstruir
el runtime interno aprobado.

## Corrección

El candidato ahora sigue esta secuencia:

1. audita el runtime fuente manteniendo bloqueos de identidad, secretos,
   extensiones y symlinks;
2. permite únicamente que el runtime interno conserve rutas absolutas;
3. copia el runtime a staging;
4. normaliza valores JSON/JSONL que sean rutas privadas absolutas completas,
   conservando solamente el nombre del archivo;
5. ejecuta nuevamente la auditoría estricta sobre staging;
6. si queda una ruta incrustada en texto libre, falla cerrado;
7. genera manifest y ZIP determinista solo desde el staging saneado.

El runtime 19K original no se modifica.

## Seguridad

La sanitización no elimina bloqueos de UNAM/PRODECON, secretos, PDFs,
Markdown, DB, claves o pesos. Tampoco autoriza publicación.

## Implementación

Como el primer intento creó `dist/public_release_candidate_19i18m`, eliminar
únicamente ese staging fallido antes de ejecutar r1. No borrar
`dist/public_safe_runtime_19i18k`.
