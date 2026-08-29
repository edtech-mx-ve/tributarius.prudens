# Sprint 19I.18J.12.2-r2 — identidad documental normalizada

El segundo bloqueo es distinto del de `cff`: el identificador canónico
`manual_derecho_fiscal_unam` no necesariamente coincide con el nombre físico
del Markdown (`Manual Derecho Fiscal.md`).

r2 mantiene resolución fail-closed, pero compara identidades exactas
normalizadas (casefold, espacios/guiones/acentos) provenientes exclusivamente
de metadatos documentales: canonical_id, filename, title, name y display_name.

No usa coincidencias por subcadena y no modifica corpus, staging, semantic-v2
ni FAISS.
