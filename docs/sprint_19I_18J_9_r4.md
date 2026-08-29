# Sprint 19I.18J.9 r4 — compatibilidad y tipado

## Incidencias corregidas
1. `prepare_batch()` devolvía tres valores pero conservaba una anotación de dos.
2. La revisión r3 eliminó accidentalmente la clave histórica
   `preserved_existing_documents`, utilizada por las pruebas y consumidores J.9.

## Corrección
- Firma tipada: `tuple[list[PreparedEvidence], list[str], list[str]]`.
- Se conserva `preserved_existing_documents` como alias compatible de
  `existing_documents`.
- `skipped_existing_pending_documents` queda separado para identificar
  específicamente documentos pendientes en J.8 que ya existían y fueron
  revalidados.
- Se centraliza la construcción/escritura del reporte para evitar divergencias
  entre `nothing_to_import` y `batch_import_completed`.

## Invariantes
- No sobrescritura.
- Revalidación SHA-256 de evidencia preexistente.
- Preflight antes de mutación.
- Fail-closed.
- `public_release_allowed=False`.
