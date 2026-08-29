# Sprint 19I.18J.11 r2 — compatibilidad con esquema real J.7

El diagnóstico J.11 asumía que J.7 siempre emitía una fila por documento con
`status=official_binary_differs_from_local_pdf`.

El reporte real J.7 usado en el proyecto conserva además la decisión en listas
de nivel superior:

- `differing_binary_documents`
- `blocked_documents`

r2 acepta ambas representaciones sin relajar el gate: el documento debe estar
explícitamente marcado como diferencia binaria por J.7.

También se normaliza la comparación SHA local a minúsculas.

No se modifica corpus, evidencia, chunks ni índices.
