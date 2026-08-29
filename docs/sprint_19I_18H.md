# Sprint 19I.18H — gate de procedencia oficial

Este sprint convierte la evidencia jurídica general de 19I.18F y la conformidad
técnica de 19I.18G en un control de procedencia por documento.

## Base oficial registrada

1. Ley Federal del Derecho de Autor, artículo 14, fracción VIII:
   `https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDA.pdf`
2. Aviso legal del Diario Oficial de la Federación:
   `https://dof.gob.mx/aviso_legal.html`

## Regla

No se infiere procedencia oficial por nombre de archivo. Cada chunk candidato
debe portar una URL explícita de fuente oficial HTTPS y una identidad coherente
`source_sha256`. Un host distinto de los permitidos, una URL ausente o una
identidad inconsistente bloquea el documento.

Este sprint es diagnóstico y fail-closed. Aunque una fuente pase la auditoría,
`promotion_ready=False` y `public_release_allowed=False`.

## Implementación

```powershell
pytest tests/test_runtime_publication_provenance_audit_19i18h.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_runtime_publication_provenance_19i18h
python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El gate 19I.18E debe continuar devolviendo código 3.
