# Sprint 19I.14 — registro de procedencia temporal fail-closed

19I.13 verificó dos fechas explícitas y ambas pertenecen a CPEUM con alcance
`amendment_specific_candidate`. LIVA no produjo fecha explícita candidata.

19I.14 materializa esa conclusión en un sidecar versionado de procedencia temporal.
No intenta convertir las fechas de reformas específicas en vigencia del documento
consolidado.

## Resultado esperado

- 2 entradas de evidencia CPEUM bloqueadas por alcance específico;
- gap de vigencia documental para CPEUM;
- gap de vigencia documental para LIVA;
- `effective_from=null`;
- `effective_to=null`;
- ninguna promoción automática.

## Implementación local

```powershell
pytest tests/test_normative_temporal_provenance_registry_19i14.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.build_temporal_provenance_registry_19i14
```

Salida:

`knowledge/temporal/temporal_provenance_registry.json`

Este sidecar será la base para una integración posterior con el motor normativo,
sin necesidad de recalcular embeddings por un cambio exclusivamente metadatos.
