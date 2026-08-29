# Sprint 19I.18J.11 r1 — corrección Ruff

Corrección exclusiva de formato E501 en la firma del helper `_fixtures`.

No cambia la lógica, clasificación ni política fail-closed del diagnóstico.

Validación esperada:

```powershell
pytest tests/test_runtime_pdf_differential_diagnostic_19i18j11.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

Después ejecutar el diagnóstico real:

```powershell
python -m scripts.diagnose_pdf_differences_19i18j11 `
  --local-corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app"
```
