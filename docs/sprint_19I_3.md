# Sprint 19I.3 — Auditoría y saneamiento de integridad normativa

## Objetivo

Auditar los subchunks reales del runtime RAG antes de modificar el corpus. El
incremento mide dos riesgos observados en la consulta IVA: contradicción entre
la unidad jurídica de metadata y el texto recuperado, y ausencia/invalidez de
metadatos temporales necesarios para aplicabilidad normativa.

## Decisión de seguridad

19I.3 **no modifica** `chunks.jsonl`, `index.faiss`, Markdown normalizado ni los
PDF fuente. El saneamiento se divide en diagnóstico trazable y reparación
posterior basada en evidencia. En particular:

- `last_reform_date` NO se convierte en `effective_from`;
- `publication_date` NO se convierte en `effective_from`;
- una contradicción explícita `Artículo metadata != Artículo texto` genera un
  candidato de cuarentena;
- la ausencia de `effective_from/effective_to` genera backlog de enriquecimiento
  verificable, no una fecha inventada;
- un subchunk sin artículo explícito en su prefijo se marca como
  `text_without_article`, no como coincidencia demostrada.

## Implementación

El analizador común `app/services/legal_unit_integrity.py` se comparte con el
puente RAG→normativa para evitar reglas divergentes.

El script:

```powershell
python -m scripts.audit_normative_integrity `
  --input "deployment/runtime_artifacts_19f/chunks.jsonl" `
  --output-dir "reports/sprint19I3" `
  --expected-total 29402
```

genera:

- `normative_integrity_report.json`: resumen global y por documento;
- `normative_integrity_findings.csv`: una fila por subchunk normativo;
- `normative_quarantine.jsonl`: contradicciones explícitas artículo↔texto;
- `normative_temporal_enrichment.jsonl`: unidades con vigencia desconocida o
  fechas inválidas.

La opción `--strict` devuelve código 2 cuando existen contradicciones
artículo↔texto o fechas temporales inválidas. No falla solo porque existan
vigencias desconocidas: esas requieren enriquecimiento jurídico posterior.

## Criterios de aceptación

1. Ruff limpio.
2. mypy sin errores.
3. suite completa pytest limpia salvo advertencias externas ya conocidas.
4. El audit real procesa exactamente 29,402 subchunks 19F.
5. Se obtiene conteo por documento de inconsistencias y cobertura temporal.
6. No se modifica ningún artefacto RAG ni corpus fuente.
7. La discrepancia LIVA observada debe aparecer en
   `normative_quarantine.jsonl` si el subchunk contiene explícitamente
   `Artículo 2-C` mientras su metadata declara `Artículo 1o`.
8. La ausencia de vigencia explícita de LIVA debe quedar en
   `normative_temporal_enrichment.jsonl`.

## Limitaciones

La comprobación estructural se concentra en identificadores explícitos de
artículo. No pretende validar automáticamente fracciones, incisos, transitorios
ni el contenido jurídico sustantivo. Un subchunk que comienza en mitad de un
artículo puede no contener un identificador explícito; se clasifica como
`text_without_article` y exige trazabilidad con su padre antes de una reparación
automática.

## Resultado esperado

El reporte real determina si la reparación debe hacerse en los chunks canónicos
19C, en la segmentación 19F, en los metadatos temporales versionados, o en más
de una capa. No se reconstruye FAISS hasta corregir la fuente del defecto.


## Hotfix r1 — acumulación de estados de consistencia

La primera ejecución real detectó un defecto en el agregador: los estados
`text_without_article` y `metadata_without_article` ya tenían claves propias en
el resumen, pero `_accumulate()` intentaba anteponerles `article_`, produciendo
`KeyError`. El hotfix usa un mapeo explícito de estados y añade validación
defensiva para estados desconocidos, además de una prueba de regresión con un
subchunk normativo que comienza a mitad de artículo.


## Hotfix r2 — tipado estricto del resumen

La validación integral local encontró tres errores mypy al aplicar `int()` sobre
valores tipados como `object` en el resumen de auditoría. El hotfix introduce
`_summary_int()`, que valida en runtime que cada contador requerido sea realmente
`int` (excluyendo `bool`) antes de usarlo. Esto elimina casts ambiguos y mantiene
la auditoría fail-closed ante reportes mal formados.
