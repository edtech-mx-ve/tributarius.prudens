# Sprint 19I.18E — gate fail-closed de publicación del runtime

El bundle runtime incluye `chunks.jsonl`, que contiene texto recuperable de las
fuentes. Publicar ese ZIP como asset público implica redistribuir dicho
contenido, aunque los PDF originales no estén dentro del ZIP.

Este incremento no decide licencias ni permisos por inferencia.

## Política

Cada `document_id` observado en el runtime debe tener:

`redistribution_status = public_redistribution_verified`

y evidencia explícita revisada. Los estados
`unknown_requires_review`, `restricted_or_internal_only` o una entrada ausente
bloquean el release público.

La política inicial deja los 16 documentos en
`unknown_requires_review`. Es intencional y fail-closed.

## Implementación

```powershell
pytest tests/test_runtime_publication_safety_audit_19i18e.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

Mientras existan fuentes no verificadas se espera `public_release_allowed=False`
y código de salida `3`.

No ejecutar `gh release create`, `git push` ni Render.
