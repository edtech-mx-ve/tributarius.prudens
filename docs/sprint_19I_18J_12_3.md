# Sprint 19I.18J.12.3 — candidato semántico transaccional

## Objetivo

Construir un nuevo candidato `semantic-v2` desde el staging oficial aprobado
por J.12.2 sin mutar el canonical vigente ni el runtime FAISS.

El pipeline reutiliza los componentes ya aceptados:

1. manifest fiscal staging de J.12.1;
2. gate de delta J.12.2;
3. `build_legal_chunks`;
4. `promote_semantic_corpus`;
5. `compare_canonical_corpora`.

El manifest staging se rebasa de forma controlada porque J.12.1 fue construido
en un directorio temporal y sus rutas absolutas originales ya no son válidas.
Las rutas se derivan exclusivamente de la estructura del manifest canónico
actual y se verifican contra los archivos reales del staging.

## Gates

- J.12.2 debe estar aprobado.
- Los reemplazos de fuente deben ser exactamente `lfdc` y
  `reg_liva_250914`.
- El conjunto de documentos semánticos no puede cambiar.
- Ningún documento distinto de los dos autorizados puede cambiar
  criptográficamente en el candidato semantic-v2.
- No hay promoción del canonical ni reconstrucción FAISS en este sprint.

## Implementación

```powershell
python -m scripts.build_selective_semantic_candidate_19i18j12_3
```

Si `dist/selective_semantic_candidate_19i18j12_3` ya existe por una ejecución
anterior fallida o deliberada, no usar `--overwrite` automáticamente: revisar
primero el resultado.

Validación:

```powershell
pytest tests/test_selective_semantic_candidate_19i18j12_3.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

## Criterios de aceptación

Se espera:

```text
unauthorized_semantic_changed_documents=
candidate_ready_for_transactional_promotion=True
canonical_mutation_performed=False
runtime_index_mutated=False
public_release_allowed=False
```

`candidate_parent_count` puede diferir de 2981 debido a los dos documentos
oficiales corregidos; no se fija artificialmente.

## Limitaciones

Este sprint acredita causalidad técnica del delta semántico. No acredita por sí
solo vigencia jurídica ni derechos de redistribución, y no habilita GitHub
Release, push ni Render.
