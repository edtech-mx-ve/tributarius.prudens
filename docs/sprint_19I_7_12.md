# Sprint 19I.7.12 — promoción canónica semántica

El saneamiento 19I.7 queda causalmente cerrado:

- 135 fronteras legítimas auditadas;
- 18 etiquetas duplicadas resueltas, `unresolved=0`;
- 25 residuos consolidados;
- 4 referencias absorbidas seguras;
- 7 de los 21 restantes resueltos por fuente↔parser;
- 14 restantes resueltos por el perfil real de chunking;
- `requires_review=0` en la última compuerta.

Este incremento aplica un gate integral y, solo si todos los controles vuelven a
ser reproducibles, copia el candidato de 2981 chunks a:

`knowledge/chunks/chunks_semantic_v2.jsonl`

El baseline 19C no se sobrescribe.

## Implementación local

```powershell
pytest tests/test_semantic_corpus_promotion_19i712.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.promote_semantic_corpus_19i712
```

No use `--overwrite` salvo regeneración deliberada después de una revisión.
