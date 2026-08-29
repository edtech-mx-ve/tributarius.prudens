# Sprint 19I.18J.12.2 — verificación del delta de reconstrucción

J.12.1 reconstruyó correctamente el corpus fiscal en staging usando las copias
oficiales de LFDC y Reglamento LIVA. El integrador reportó los SHA oficiales
esperados para ambos documentos y no mutó semantic-v2 ni FAISS.

J.12.2 compara el manifest y Markdown normalizado actuales contra el staging.
El gate solo permite avanzar si:

- el conjunto de 15 documentos fiscales es idéntico;
- LFDC y Reglamento LIVA cambian de SHA de fuente;
- ningún otro documento cambia de fuente ni Markdown normalizado;
- no se realiza todavía promoción canónica.

## Implementación

```powershell
python -m scripts.verify_selective_rebuild_delta_19i18j12_2
```

Luego:

```powershell
pytest tests/test_selective_rebuild_delta_19i18j12_2.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

Resultado esperado:

- `source_changed_documents=lfdc,reg_liva_250914`
- `unauthorized_changed_documents=`
- `delta_safe_for_candidate_build=True`
- `canonical_mutation_performed=False`
- `public_release_allowed=False`

Si el Markdown de cualquier documento no autorizado cambia, el proceso se
detiene antes de construir el nuevo candidato semántico.
