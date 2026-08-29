# Sprint 19I.9 hotfix r1

El primer smoke E2E reveló dos defectos distintos:

1. El verificador buscaba `document_id` dentro de `metadata`, mientras el presenter
   19I lo expone a nivel superior. Esto generó falsos negativos para LIVA/CPEUM.
2. El enriquecimiento dirigido 19G solo consultaba el documento ruteado si estaba
   completamente ausente del pool semántico. Si aparecía débilmente en top-100,
   no solicitaba sus mejores candidatos filtrados. Esto dejó fuera a LIEPS en una
   consulta natural aunque el benchmark explícito sí lo recuperaba.

La corrección:
- normaliza `document_id` plano y fallback `source_reference=.md`;
- ejecuta enriquecimiento dirigido para toda ruta documental explícita;
- mantiene deduplicación posterior;
- no cambia embeddings ni FAISS.

## Implementación local

```powershell
pytest tests/test_semantic_runtime_smoke_19i9.py tests/test_legal_hybrid_retrieval.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.evaluate_semantic_runtime_19i8 --local-files-only
python -m scripts.smoke_semantic_runtime_19i9 --local-files-only
```
