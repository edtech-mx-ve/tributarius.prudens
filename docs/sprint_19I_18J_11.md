# Sprint 19I.18J.11 — diagnóstico diferencial LFDC / Reglamento LIVA

## Objetivo

Analizar únicamente los dos documentos que J.7 marcó como
`official_binary_differs_from_local_pdf`:

- `lfdc`
- `reg_liva_250914`

No modifica PDFs, chunks, índices, metadatos ni políticas.

## Método

1. Revalida ambos PDFs como archivos regulares `%PDF-`.
2. Calcula SHA-256 y tamaño.
3. Extrae texto con `pypdf` o `PyPDF2` ya disponibles en el entorno.
4. Normaliza ruido de maquetación:
   - espacios;
   - saltos;
   - guiones de corte de línea;
   - casefold.
5. Compara hash de texto normalizado.
6. Calcula similitud Dice por multiconjunto de tokens.
7. Clasifica de forma fail-closed.

Clasificaciones:

- `binary_or_layout_difference_textually_equivalent`
- `near_textual_equivalence_requires_manual_review`
- `material_textual_difference_detected`

Una equivalencia textual no se presenta como identidad binaria y no concede
derechos de redistribución.

## Implementación

```powershell
python -m scripts.diagnose_pdf_differences_19i18j11 `
  --local-corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app"
```

Reporte:

`reports/sprint19I18J11/pdf_differential_diagnostic.json`

Si aparece `material_textual_difference_detected`, no reemplazar archivos:
se deberá preparar una reconstrucción selectiva y trazable de ese documento.

## Pruebas

```powershell
pytest tests/test_runtime_pdf_differential_diagnostic_19i18j11.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

## Seguridad

- no escritura sobre corpus;
- no auto-promoción;
- no publicación;
- no Git push;
- no GitHub Release;
- no Render.
