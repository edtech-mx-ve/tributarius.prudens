# Sprint 19I.18J — procedencia `PDF local → fuente oficial`

## Objetivo

Cerrar el siguiente eslabón de cadena de custodia sin inferencias:

`runtime → SHA-256 → PDF local → descarga HTTPS de autoridad → SHA-256`

19I.18I ya demostró que los 14 conjuntos de chunks normativos derivan
exactamente de 14 PDFs locales. 19I.18J descarga candidatos exclusivamente de
hosts oficiales permitidos y exige coincidencia SHA-256 exacta.

## Seguridad

- solo HTTPS;
- allowlist de hosts Cámara de Diputados y DOF;
- se valida también el host final después de redirects;
- timeout configurable;
- límite de tamaño configurable;
- la respuesta debe iniciar con `%PDF-`;
- hash distinto no se interpreta como equivalente;
- un fallo de red no se interpreta como evidencia;
- no se modifica el corpus, runtime, FAISS ni política 19I.18E;
- `public_release_allowed=False` y `promotion_ready_documents=[]`.

## Candidatos oficiales

La registry contiene URLs oficiales candidatas. No se consideran verificadas
por aparecer en la registry: la verificación ocurre exclusivamente por igualdad
criptográfica con el PDF local enlazado en 19I.18I.

## Implementación

```powershell
pytest tests/test_runtime_official_source_audit_19i18j.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.audit_runtime_official_source_19i18j

python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El reporte queda en:

`reports/sprint19I18J/runtime_official_source_provenance.json`

El auditor 19I.18E debe seguir devolviendo código 3.


## Hotfix r1

Corrección de compatibilidad Ruff/UP035: `Callable` se importa desde
`collections.abc` en Python 3.12. No cambia comportamiento ni política.


## Hotfix r2

Ordena el bloque de imports conforme a Ruff I001. Sin cambios funcionales.
