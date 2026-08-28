# Artefactos RAG de runtime

Esta carpeta es el punto de montaje lógico para artefactos RAG preconstruidos.

Para un despliegue con RAG habilitado deben existir:

- `index.faiss`
- `chunks.jsonl`
- `manifest.json`

El Sprint 19 no genera embeddings en Render. La construcción pesada se realiza
offline o en CI controlado y los artefactos se validan antes de incorporarlos
a una release. El perfil gratuito actual mantiene `REQUIRE_RAG_ARTIFACTS=false`
porque el runtime web todavía debe poder arrancar sin inventar resultados.

No guardar datos sensibles, secretos ni expedientes de contribuyentes aquí.
