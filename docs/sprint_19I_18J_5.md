# Sprint 19I.18J.5 — plan ejecutable de remediación de publicación

## Objetivo

Convertir los resultados reales de 19I.18J.3 y 19I.18J.4 en una cola
determinista de acciones, sin mezclar decisiones técnicas con decisiones
jurídicas o de licencia.

Con el estado actual el plan debe producir:

- Track A: 13 documentos normativos con procedencia oficial pendiente;
- Track B: `rmf_2026`, cuya procedencia exacta ya está verificada pero cuya
  política de redistribución sigue pendiente;
- Track C: UNAM y PRODECON, que requieren licencia/autorización explícita o
  exclusión del runtime público;
- Git push, GitHub Release y Render siguen bloqueados.

## Implementación

```powershell
pytest tests/test_runtime_publication_remediation_plan_19i18j5.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.build_runtime_publication_remediation_plan_19i18j5
```

Salida:

`reports/sprint19I18J5/runtime_publication_remediation_plan.json`

## Criterios de aceptación

- prioriza procedencia oficial antes de cualquier publicación;
- no automatiza decisiones jurídicas ni de licencia;
- no modifica corpus, policy registries ni runtime;
- no habilita release o Render;
- mantiene fail-closed;
- valida cobertura exacta de documentos.
