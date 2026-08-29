# Sprint 19I.18J.12.3-r1 — identidad de parent chunks

El primer intento funcional llegó hasta la auditoría criptográfica del
candidato y falló con `Chunk sin metadata`.

La causa es una suposición incorrecta del auditor nuevo: exigía que la
identidad documental estuviera anidada en `metadata`, mientras que los parent
chunks canónicos del pipeline existente pueden conservarla en el nivel
superior.

r1 reconoce, en orden fail-closed:

1. `document_id` top-level;
2. `canonical_id` top-level;
3. `source_document_id` top-level;
4. los mismos campos dentro de `metadata`.

No se infiere identidad por texto, nombre de chunk ni prefijos. Si ninguna
identidad explícita existe, el gate sigue fallando.

No cambia J.12.1/J.12.2, no muta semantic-v2, no reconstruye FAISS y no
habilita publicación.
