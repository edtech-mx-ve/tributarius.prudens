# Sprint 19E hotfix r1

Corrige los fallos de validación estática y fixtures detectados al aplicar 19E:

- fixtures `document_id` respetan longitud mínima del dominio;
- fixture `chunk_id` respeta longitud mínima del dominio;
- `TokenCounterLike` pasa a `typing.Protocol`, permitiendo tipado estructural del embedder;
- se evita reutilizar `item` con tipos incompatibles en el CLI de evaluación;
- se corrigen las líneas E501 de ambos CLI.

No cambia el índice FAISS 19D ni requiere reconstruir embeddings.
