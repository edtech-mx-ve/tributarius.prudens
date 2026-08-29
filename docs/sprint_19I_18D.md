# Sprint 19I.18D — plan local de publicación del runtime

El runtime aprobado ocupa 46,365,541 bytes. No se incorpora al historial Git.
Este incremento prepara un plan local para publicarlo posteriormente como asset
de un GitHub Release.

La publicación todavía no se ejecuta.

## Artefacto fijado

- SHA-256:
  `687c9f6bba0b166b3728ce387d560644523d260cde1f7a298655954e490cbda4`
- asset:
  `tributarius-prudens-runtime-semantic-v2.zip`
- tag propuesto:
  `runtime-semantic-v2-19i18`
- repositorio:
  `edtech-mx-ve/tributarius.prudens`

## Implementación

```powershell
pytest tests/test_runtime_release_publication_plan_19i18d.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.prepare_runtime_release_publication_19i18d
```

El comando escribe únicamente bajo `dist/`, por lo que el plan y las notas no
se incorporan al repositorio.

No ejecutar aún el comando `gh release create`.
