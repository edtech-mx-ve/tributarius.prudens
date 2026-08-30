# Sprint 19I.18S-r10.3.1 — hotfix de extracción de fuente

Corrige un defecto del paquete r10.3: la generación del parche tomó como ancla
una mención del nombre de archivo dentro de la salida de PowerShell, por lo que
`public_release_cold_start_19i18n.py` incorporó contenido previo y un separador
`====================`, provocando `SyntaxError` durante collection.

Este hotfix reemplaza únicamente:
- `app/services/public_release_cold_start_19i18n.py`
- `scripts/validate_deployment.py`

Ambos se reconstruyen desde sus encabezados de sección exactos y conservan el
nuevo pin SHA-256:

`18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514`

No cambia la lógica del instalador r10.3 ni el artefacto público r10.
