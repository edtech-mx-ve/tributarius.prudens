# Sprint 19I.18J.6 — evidencia oficial adquirida mediante navegador

## Motivo

La red local no permite conexiones TCP a `www.diputados.gob.mx`, mientras
que el navegador Opera con VPN sí permite abrir el PDF oficial. La VPN del
navegador no se usa como supuesto para Python.

Este incremento permite importar de forma controlada un PDF descargado
manualmente desde una URL ya incluida en el registro oficial 19I.18J.

## Controles

- `document_id` debe estar en la allowlist 19I.18J;
- archivo existente, límite de tamaño y cabecera `%PDF-`;
- SHA-256 antes y después de la copia;
- no sobrescribe evidencia;
- manifiesto determinista por `document_id`;
- conserva la URL oficial registrada;
- no declara equivalencia con el PDF local;
- no concede derechos de redistribución.

## Implementación

Después de descargar `CFF.pdf` desde la URL oficial en Opera, suponiendo que
Windows lo guardó en `Downloads`:

```powershell
python -m scripts.import_browser_official_evidence_19i18j6 `
  --document-id cff `
  --input-pdf "$env:USERPROFILE\Downloads\CFF.pdf"
```

Validación:

```powershell
pytest tests/test_runtime_browser_official_evidence_19i18j6.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

La evidencia se guarda por defecto en:

`dist/browser_official_evidence_19i18j6/`

## Criterio de aceptación

El importador debe registrar SHA-256 y tamaño del PDF oficial sin inferir que
coincide con el PDF local. La comparación criptográfica es un gate posterior.
