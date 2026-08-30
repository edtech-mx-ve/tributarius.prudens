# Sprint 19I.18S-r16B.0.1 — JSON media-type hotfix

El gate r16B detectó dos defectos locales, sin impacto en producción:

1. imports no usados en el middleware;
2. el middleware preservaba `application/json` sin declarar explícitamente
   `charset=utf-8`, aunque el cuerpo ya se serializaba como UTF-8.

La corrección elimina imports muertos y, únicamente para respuestas JSON
normalizadas, sustituye `Content-Type` por `application/json; charset=utf-8`
y recalcula `Content-Length`.

No modifica `app/main.py`, runtime r10, RAG, política temporal, Render ni
dependencias.
