# Sprint 19I.18J.12.2-r1 — resolución exacta de Markdown

El primer J.12.2 detectó dos candidatos para `cff` porque la búsqueda por
subcadena confundía `cff` con nombres como `reg_cff`. r1 elimina esa
heurística ambigua.

Orden de resolución:

1. ruta explícita del manifest, si existe y es única;
2. stem exacto igual al `canonical_id`;
3. stem exacto del `filename` fuente;
4. fail-closed si no existe resolución exacta o hay duplicados.

No se selecciona nunca el primer candidato por conveniencia. El hotfix no
modifica corpus, staging, semantic-v2 ni FAISS.
