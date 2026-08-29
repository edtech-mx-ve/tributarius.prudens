# Sprint 19I.18J.9.1 — control de preparación de descargas oficiales

## Objetivo
Separar claramente la adquisición manual en Opera de la importación J.9.

El control lee el plan J.8 y el manifest J.6. Los documentos ya incorporados
como evidencia se consideran disponibles; los restantes se verifican en el
directorio de descargas.

## Validaciones
- archivo regular;
- tamaño mayor que cero y máximo de 50 MiB;
- cabecera `%PDF-`;
- SHA-256;
- reporte trazable por documento.

No modifica el manifest ni copia archivos.

## Implementación

```powershell
python -m scripts.check_browser_acquisition_readiness_19i18j9_1 `
  --downloads-dir "$env:USERPROFILE\Downloads"
```

Mientras falten documentos devuelve código 3 e imprime la URL y el nombre de
archivo exacto. Cuando todos estén presentes y sean PDFs válidos:
`batch_import_allowed=True`.

Después:

```powershell
python -m scripts.import_browser_official_evidence_batch_19i18j9 `
  --downloads-dir "$env:USERPROFILE\Downloads"

python -m scripts.audit_browser_official_evidence_19i18j7
```

## Seguridad
Este control no demuestra identidad binaria contra el corpus ni derechos de
redistribución. `public_release_allowed=False`.
