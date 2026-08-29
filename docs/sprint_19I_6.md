# Sprint 19I.6 — Reparación canónica quirúrgica

Objetivo: sanear exclusivamente los prefijos contaminantes de los padres
canónicos CFF artículo 31 y LIVA artículo 18, sin sobrescribir el corpus
original ni reconstruir todavía 19F/embeddings/FAISS.

El detector 19I.5 ahora reconoce encabezados Markdown (`### Artículo N.-`) y
evita retroceder desde `31-A` para interpretar erróneamente `31-` como si fuera
el separador de un encabezado de artículo 31.

## Implementación local

Dry-run:

```powershell
python -m scripts.repair_canonical_prefixes
```

Esperado: 3174 chunks, 2 candidatos y ambos `repairable=True` con razón
`prefix_contamination_before_matching_heading`.

Solo después:

```powershell
python -m scripts.repair_canonical_prefixes --apply
```

La copia se escribe en `knowledge/chunks/chunks_19i6_repaired.jsonl`. El input
`knowledge/chunks/chunks.jsonl` permanece intacto. La herramienta rechaza una
salida ya existente y valida cardinalidad después de escribir.
