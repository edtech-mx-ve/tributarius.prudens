# Sprint 19I.7.2 — refinamiento de artículos numéricos absorbidos

La auditoría 19I.7.1 encontró 149 unidades clasificadas como
`absorbed_numeric_article_requires_review`. Antes de promover el candidato se
debe separar artículos probablemente legítimos de referencias numéricas que 19C
había segmentado como si fueran encabezados.

## Clasificación

- `probable_legitimate_article_boundary`: encabezado fuerte y cuerpo sustantivo.
- `reference_like_false_boundary`: la línea continúa como referencia (`de`, `del`,
  `fracción`, `párrafo`, etc.).
- `reform_or_transitory_context`: contexto de reforma/transitorio sin encabezado fuerte.
- `short_heading_candidate_requires_review`: encabezado fuerte pero fragmento corto.
- `ambiguous_numeric_boundary_requires_review`: resto de casos.

La auditoría verifica además que el texto del chunk retirado esté realmente
contenido en el chunk candidato que lo absorbió.

## Implementación local

```powershell
pytest tests/test_absorbed_numeric_audit_19i72.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_absorbed_numeric_19i72
```

Salidas:

- `reports/sprint19I72/absorbed_numeric_audit.json`
- `reports/sprint19I72/absorbed_numeric_findings.csv`

No se modifica 19C, el candidato 19I.7 ni FAISS.
