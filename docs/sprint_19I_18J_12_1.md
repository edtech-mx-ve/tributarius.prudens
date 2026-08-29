# Sprint 19I.18J.12.1 — reconstrucción aislada desde evidencia oficial

El pipeline inspeccionado confirma que `integrate_fiscal_corpus.py` permite
dirigir `normalized-root`, metadata y manifest a rutas de staging, mientras que
la reconstrucción semántica posterior consume el corpus promovido. Por ello
J.12.1 ejecuta la primera mutación **solo en un workspace aislado**, no sobre
`knowledge/` ni sobre el corpus fuente. fileciteturn36file0

## Controles

- acepta exclusivamente `lfdc` y `reg_liva_250914`;
- valida PDF y SHA-256 de fuente local y evidencia oficial;
- copia el corpus a staging;
- localiza los dos PDF por SHA, no por nombre;
- reemplaza únicamente las copias de staging;
- reutiliza `scripts.integrate_fiscal_corpus`;
- no toca semantic-v2, subchunks ni FAISS;
- mantiene publicación, GitHub y Render bloqueados.

## Implementación

```powershell
python -m scripts.stage_selective_official_rebuild_19i18j12_1 `
  --local-corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app"
```

Si ya existe una salida de una ejecución deliberada anterior:

```powershell
python -m scripts.stage_selective_official_rebuild_19i18j12_1 `
  --local-corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app" `
  --overwrite
```

Resultado esperado: `dist/selective_rebuild_19i18j12_1` con corpus temporal,
Markdown/metadata reconstruidos y `rebuild_audit.json`.

J.12.2 podrá comparar el staging contra semantic-v2 y promover
transaccionalmente solo después de validar el delta.
