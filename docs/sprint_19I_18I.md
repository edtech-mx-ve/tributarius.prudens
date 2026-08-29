# Sprint 19I.18I — puente de integridad runtime → PDF fuente

19I.18H confirmó que los chunks del runtime no conservan `source_url`. No se
debe inventar ni insertar una URL oficial en 26,101 chunks sin demostrar antes
qué archivo fuente produjo cada uno.

Este sprint verifica una capa anterior de la cadena de custodia:

`runtime chunk -> source_filename + source_sha256 -> PDF fuente local`

Para cada uno de los 14 documentos normativos se calcula SHA-256 sobre el PDF
real del corpus local y se compara con el único `source_sha256` conservado por
todos sus chunks.

Un match establece que el runtime deriva del mismo archivo binario local.
No prueba todavía que ese archivo haya sido descargado de una autoridad
oficial; por eso `public_release_allowed=False` permanece fail-closed.

## Implementación

```powershell
pytest tests/test_runtime_source_bridge_audit_19i18i.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.audit_runtime_source_bridge_19i18i `
  --corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app"

python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El auditor 19I.18E debe continuar terminando con código 3.


## Hotfix r1

El diagnóstico real mostró que `source_filename` usa identificadores/nombres
distintos a los nombres físicos de los PDFs del corpus. El filename no es una
prueba criptográfica y no debe bloquear una coincidencia de contenido.

El auditor ahora construye un índice SHA-256 de todos los PDFs del corpus y
resuelve en este orden:

1. coincidencia exacta de nombre + SHA-256;
2. si el nombre no coincide, coincidencia SHA-256 única;
3. si el hash no existe o es ambiguo, fail-closed.

`filename_match=False` puede coexistir con `bridge_verified=True` cuando el PDF
se resuelve inequívocamente por SHA-256. Esto conserva una cadena de custodia
más fuerte que la coincidencia nominal.
