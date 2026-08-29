# Sprint 19I.18K-r2 — alias canónico PRODECON

El primer gate funcional 19I.18K falló correctamente con:

`Documentos desconocidos en canonical: ['prodecon_contribuyente']`

El canonical real identifica la capa PRODECON como
`prodecon_contribuyente`, mientras que el gate público utilizaba el nombre
lógico `prodecon`.

Este hotfix añade únicamente una normalización explícita y cerrada:

- `prodecon_contribuyente` -> `prodecon`
- `manual_derecho_fiscal_unam` -> `manual_unam`

No se usan prefijos, substrings, fuzzy matching ni heurísticas.

La auditoría de artefactos también reconoce y bloquea las identidades físicas
originales para impedir que sobrevivan en canonical, retrieval o runtime
públicos.

Importante: el intento fallido creó `dist/public_safe_runtime_19i18k` antes de
detectar el alias. Ese staging incompleto debe eliminarse deliberadamente antes
de reintentar, porque el servicio rechaza por diseño un output preexistente.
No se modifica el runtime interno.
