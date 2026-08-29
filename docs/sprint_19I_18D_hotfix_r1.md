# Sprint 19I.18D hotfix r1

Corrige exclusivamente Ruff/I001 en
`scripts/prepare_runtime_release_publication_19i18d.py`.

La causa es el espaciado entre el bloque de imports y la constante de módulo.
No cambia la lógica del plan de publicación, el repositorio, el tag, el asset,
el SHA-256 aprobado ni ejecuta publicación remota.

## Validación

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.prepare_runtime_release_publication_19i18d
```
