# Sprint 19I.18K — runtime público seguro + aceptación jurídica/técnica local

## Objetivo

Construir un runtime local separado del runtime interno completo.

La composición pública se limita a 14 fuentes normativas:

`cff, cpeum, lfdc, lfisan, lfpca, lieps, lif_2026, lisr, liva, lotfja,
reg_cff, reg_lisr_060516, reg_liva_250914, rmf_2026`.

Se excluyen materialmente del canonical, subchunks e índice:

- `manual_unam`;
- `prodecon`.

La exclusión no consiste en borrar artefactos del runtime vigente. Se genera un
canonical nuevo y se reconstruyen embeddings/FAISS desde cero en `dist/`.

## Gate criptográfico

El input debe ser exactamente el canonical promovido por J.12.4:

`4d040043173c625ca09ed2ae954aa2bdf01993989f1a52997d7acbb067fee25c`

## Aceptación técnica

El sprint:

1. filtra el canonical a normative-only;
2. genera manifest público;
3. deriva del benchmark existente solo los casos cuya expectativa documental
   pertenece a las 14 fuentes normativas;
4. reconstruye retrieval subchunks y FAISS con el pipeline 19I.8;
5. ejecuta el evaluador 19G;
6. escanea artefactos textuales para impedir que UNAM/PRODECON permanezcan
   etiquetados como documentos recuperables.

Los umbrales conservan el baseline aceptado para las métricas disponibles:

- Hit@1/3/K(any) = 1.0
- MRR(any) = 1.0
- PrimaryHit@1 >= 0.917
- PrimaryHit@3 >= 0.917
- PrimaryHit@K = 1.0
- PrimaryMRR >= 0.938

`MeanUniqueDocs@K` se reporta, pero no bloquea: al retirar dos capas completas
de conocimiento puede cambiar legítimamente la diversidad del top-k.

## Gate jurídico local

Este sprint **no emite una conclusión jurídica automática de redistribución**.

La clasificación local es:

- 14 textos normativos: candidatos a exclusión autoral de texto oficial
  conforme al análisis previo de LFDA art. 14 VIII, sujetos a revisión humana
  final de fidelidad/procedencia y alcance de redistribución;
- UNAM: excluido públicamente mientras no exista licencia/permiso acreditado;
- PRODECON: excluido públicamente mientras no exista licencia/permiso
  acreditado;
- vigencia temporal: gate separado, todavía incompleto.

Por eso aun con aceptación técnica:

`public_release_allowed=False`.

## Implementación

```powershell
pytest tests/test_public_safe_runtime_19i18k.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

Luego:

```powershell
python -m scripts.build_public_safe_runtime_19i18k
```

La reconstrucción puede tardar en CPU.

No ejecutar Git/GitHub Release/Render.

## Resultado esperado

```text
scope=normative_only
normative_document_count=14
excluded_documents=manual_unam,prodecon
benchmark_passed=True
blocked_content_absent=True
technical_local_acceptance=True
redistribution_human_review_required=True
temporal_validity_complete=False
public_release_allowed=False
```

## Criterios de aceptación

- exactamente 14 documentos normativos;
- ninguna identidad documental UNAM/PRODECON en canonical/retrieval/runtime;
- benchmark normativo sobre el umbral;
- canonical interno de 2981 parents no se modifica;
- runtime interno no se modifica;
- no hay promoción jurídica automática;
- no hay publicación.

## Limitaciones

Un runtime normativo técnicamente seguro no equivale a afirmar vigencia
temporal completa ni autorización jurídica definitiva de redistribución.
Esos gates permanecen separados y fail-closed.
