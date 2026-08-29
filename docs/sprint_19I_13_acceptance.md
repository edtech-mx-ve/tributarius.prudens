# Aceptación Sprint 19I.13

- procesa exclusivamente candidatos con `explicit_date_signal`;
- valida que la ruta y línea de la fuente normalizada existan;
- incorpora contexto anterior y posterior;
- clasifica alcance como documento completo, reforma específica o ambiguo;
- no escribe `effective_from`/`effective_to`;
- `promotion_ready=0`;
- no modifica artefactos RAG ni runtime.
