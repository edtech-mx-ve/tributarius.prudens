# Sprint 19I.18F — evidencia jurídica para publicación

El gate 19I.18E permanece cerrado. Este sprint reduce la incertidumbre sin
promover fuentes automáticamente.

## Evidencia oficial

La Ley Federal del Derecho de Autor, artículo 14, fracción VIII, establece que
los textos legislativos, reglamentarios, administrativos o judiciales y sus
traducciones oficiales no son objeto de protección autoral; las concordancias,
interpretaciones, estudios, anotaciones, comentarios y trabajos originales
similares sí pueden estar protegidos.

Fuente oficial:
`https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDA.pdf`

## Clasificación

- 14 documentos normativos: `statutory_text_exclusion_candidate`.
- Manual UNAM: `separate_license_review_required`.
- PRODECON: `separate_license_review_required`.

Ningún estado de `runtime_publication_policy_19i18e.json` cambia todavía.

## Implementación

```powershell
pytest tests/test_runtime_publication_evidence_audit_19i18f.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_runtime_publication_evidence_19i18f
python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El segundo auditor debe continuar con salida 3 hasta una promoción posterior
basada en evidencia y conformidad del contenido.
