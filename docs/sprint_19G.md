# Sprint 19G — Recuperación híbrida y reranking jurídico

## Objetivo

Corregir la debilidad identificada en 19F.1: la similitud vectorial recupera
contenido semánticamente bueno, pero puede anteponer doctrina u orientación a
la fuente jurídica primaria. Sprint 19G no reconstruye embeddings ni FAISS.
Trabaja sobre `deployment/runtime_artifacts_19f`.

## Diseño

Pipeline:

1. recuperación semántica amplia con FAISS;
2. clasificación determinista de modo de consulta: normativa, doctrinal o neutral;
3. enrutamiento documental mediante una política JSON versionable;
4. enriquecimiento dirigido únicamente si una fuente inferida no aparece en el
   pool semántico;
5. score léxico reproducible;
6. score de autoridad jurídica condicionado al modo normativo;
7. score doctrinal condicionado al modo doctrinal;
8. límite de monopolio documental en top-k;
9. trazabilidad por resultado: vector, léxico, ruta, autoridad, doctrina y score final.

No se usa `eval`, código dinámico, red ni servicios comerciales.

## Política

`app/resources/legal_retrieval_policy.json` contiene pesos, roles, marcadores y
rutas documentales. Las rutas son señales explicables; no sustituyen el análisis
de vigencia normativa ni convierten una fuente en aplicable por sí mismas.

## Criterios de aceptación

Sobre el benchmark congelado de 12 casos:

- `PrimaryHit@K` debe ser superior al 0.833 de 19F.1;
- `PrimaryMRR` debe ser superior al 0.778 de 19F.1;
- CPEUM debe aparecer en top-k para `cpeum_principios`;
- LIVA debe aparecer en top-k para `liva_tasa`;
- ningún caso que ya tenía fuente primaria en top-k puede perderla;
- no se reconstruyen los 29,402 embeddings;
- el comportamiento doctrinal de UNAM no debe ser desplazado por una regla
  global de autoridad.

El script de comparación devuelve código distinto de cero si falla alguno de
los criterios estructurales anteriores.

## Implementación local

Desde la raíz del repositorio:

```powershell
pytest tests/test_legal_hybrid_retrieval.py -v
ruff check . --fix
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

Luego evaluar 19G:

```powershell
python -m scripts.evaluate_runtime_retrieval_19g `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --local-files-only
```

Comparar contra 19F.1:

```powershell
python -m scripts.compare_runtime_retrieval_19g `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --local-files-only
```

Inspección trazable LIVA:

```powershell
python -m scripts.query_runtime_rag_19g `
  "Ley del IVA tasa general impuesto al valor agregado actos gravados" `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --top-k 10 `
  --local-files-only
```

Inspección trazable CPEUM:

```powershell
python -m scripts.query_runtime_rag_19g `
  "principios constitucionales tributarios proporcionalidad equidad legalidad contribuciones" `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --top-k 10 `
  --local-files-only
```

## Resultado esperado

La evaluación debe mostrar la fuente primaria dentro del top-k en los 12 casos
y una mejora de `PrimaryHit@K` y `PrimaryMRR`. Los scripts de consulta muestran
por hit el score vectorial y las contribuciones del reranking.

## Limitaciones

La política de rutas documentales es explícita y versionada; no reemplaza
clasificación jurídica avanzada. El enriquecimiento dirigido puede ser más
costoso cuando una fuente inferida está fuera del pool semántico, porque el
retriever FAISS actual aplica filtros después de ampliar la búsqueda. Esto se
medirá antes de llevar 19G al runtime público.

Sprint 19G es local hasta superar pruebas, benchmark, inspección de casos y
auditoría. No hacer commit, push ni despliegue Render antes de su aceptación.
