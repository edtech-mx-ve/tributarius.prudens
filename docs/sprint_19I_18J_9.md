# Sprint 19I.18J.9 — Importación por lote de evidencia oficial descargada en navegador

## Objetivo
Reducir la operación manual después de descargar con Opera los PDFs pendientes del plan J.8.

## Flujo
J.8 plan → descargas manuales → J.9 preflight integral → staging → manifest/evidencia → J.7 comparación criptográfica.

## Seguridad
- No realiza red ni automatiza Opera/VPN.
- Solo procesa los documentos `pending_browser_download` de J.8.
- Requiere URL registrada bajo `https://www.diputados.gob.mx/`.
- Valida archivo regular, tamaño máximo, cabecera `%PDF-` y SHA-256.
- Valida el lote completo antes de mutar evidencia.
- No sobrescribe evidencia existente.
- Mantiene CFF/CPEUM ya importados.
- No concede derechos de redistribución, vigencia ni autorización de publicación.

## Implementación
Después de descargar todos los PDFs pendientes con los nombres de J.8:

```powershell
python -m scripts.import_browser_official_evidence_batch_19i18j9 `
  --downloads-dir "$env:USERPROFILE\Downloads"

python -m scripts.audit_browser_official_evidence_19i18j7
```

## Resultado esperado
El primer comando importa todos los pendientes de J.8 de una vez. El segundo compara todas las evidencias con los PDFs locales.
