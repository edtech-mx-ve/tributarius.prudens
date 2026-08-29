# Sprint 19I.7.7 — prioridad de evidencia en etiquetas duplicadas

19I.7.6 aisló un único caso: CFF, Artículo 21. Dos candidatos compartían un
prefijo largo, pero solo uno contenía íntegramente el texto 19C y además cubría
las páginas 320–324.

La causa era el orden del heurístico de 19I.7.5: un prefijo de 160 caracteres se
trataba como “content match” al mismo nivel que la contención completa.

La corrección aplica jerarquía de evidencia:

1. contención textual completa única;
2. solapamiento de página único;
3. prefijo sustantivo único;
4. abstención.

No modifica corpus, candidato, embeddings ni FAISS.

## Implementación

```powershell
pytest tests/test_legal_duplicate_boundary_audit_19i75.py `
       tests/test_legal_duplicate_boundary_resolution_19i77.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_duplicate_boundaries_19i75
python -m scripts.audit_unresolved_boundary_19i76
```
