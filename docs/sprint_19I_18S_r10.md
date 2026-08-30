# Sprint 19I.18S-r10 — integridad interna del candidato público

## Objetivo
Cerrar la brecha detectada entre la integridad exterior del ZIP 19M y el
`manifest.json` interno consumido por `FaissRetriever`.

## Causa
El saneamiento público reserializa JSON/JSONL. El `chunks.jsonl` final quedó con
bytes distintos de los registrados previamente en `manifest.chunks_sha256`.
El `release_manifest.json` exterior sí describía los bytes finales, por lo que
las validaciones de bundle/cold-start no detectaban la inconsistencia interna.

## Estrategia
Este incremento no desactiva ninguna validación. Repara únicamente
`chunks_sha256` y `chunks_bytes` a partir del `chunks.jsonl` final, después de
comprobar que:
- `index.faiss` conserva el SHA y tamaño aprobados por el manifest interno;
- número de registros JSONL == FAISS `ntotal`;
- `manifest.chunk_count` coincide;
- dimensión FAISS == `manifest.vector_dimension`.

Después reconstruye el `release_manifest.json` exterior, genera un ZIP nuevo y
vuelve a validar el artefacto empaquetado.

El candidato original no se sobrescribe.

## Criterios de aceptación
1. El candidato original inconsistente es rechazado por `validate_candidate`.
2. El candidato reparado satisface integridad interna y exterior.
3. `chunk_count == index.ntotal`.
4. La dimensión del índice coincide con el manifest.
5. El SHA de `index.faiss` no cambia respecto al manifest aprobado.
6. El ZIP reparado tiene un SHA nuevo y debe publicarse como un asset/versionado
   nuevo; nunca sustituirse silenciosamente bajo el SHA anterior.

## Limitación
r10 es una reparación segura del candidato ya publicado. La prevención
estructural en el constructor 19M debe incorporar la misma validación
post-saneamiento antes de futuras reconstrucciones.
