# Sprint 19I.18S-r15.1

Hotfix local para compatibilidad de `QueryAnalysis.facts`.

El fallo focalizado de r15 mostró que `model_copy(update=...)` puede dejar
diccionarios dentro de `facts`. El helper de este incremento admite tanto
objetos tipados como mappings y falla de forma cerrada ante entradas
malformadas.

## Integración

En `app/services/hybrid_orchestrator.py`:

1. importar `query_fact_value` desde
   `app.services.query_fact_compat_19s_r15`;
2. sustituir el cuerpo de `_query_matter` por:

```python
def _query_matter(analysis: QueryAnalysis) -> str | None:
    return query_fact_value(analysis.facts, "matter")
```

No cambia la política de aplicabilidad; únicamente elimina la suposición
insegura de que todo elemento de `facts` tiene atributos.
