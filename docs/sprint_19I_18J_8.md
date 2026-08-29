# Sprint 19I.18J.8 — Plan confiable de descarga oficial mediante Opera

## Objetivo

Generar desde el registro oficial existente un plan reproducible para los
documentos alojados en `www.diputados.gob.mx`, evitando búsquedas web,
mirrors y URLs introducidas manualmente.

El plan distingue:

- `exact_binary_verified`: ya verificado por J.7;
- `imported_pending_bridge_audit`: importado por J.6 pero aún no comparado;
- `pending_browser_download`: pendiente de descarga por navegador.

## Procedimiento operativo

Para cada documento pendiente:

1. Abrir exactamente la URL mostrada por el script en Opera con VPN activo.
2. Usar el botón de descarga del visor PDF.
3. Guardar con el nombre exacto indicado.
4. Importar con el comando generado.
5. No usar “Imprimir → Guardar como PDF”.

El plan se escribe en:

`reports/sprint19I18J8/browser_official_download_plan.json`

## Límites

Este sprint no automatiza Opera, no descarga por Python y no altera la política
de publicación. Procedencia binaria, redistribución, vigencia temporal y
publicación continúan siendo controles independientes.
