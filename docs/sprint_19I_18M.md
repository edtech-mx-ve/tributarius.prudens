# Sprint 19I.18M — bundle reproducible y auditoría integral local

## Objetivo

Construir un **candidato local** de distribución a partir del runtime público
normative-only aprobado en 19K y del gate jurídico/temporal 19L.

Este sprint NO publica nada.

## Entrada

- runtime 19K: 2962 parents;
- canonical SHA256:
  `7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0`;
- procedencia 19L completa;
- temporal fail-closed completo;
- vigencia temporal global incompleta;
- redistribución todavía pendiente de revisión humana.

## Alcance del bundle

El ZIP contiene únicamente:

- `runtime/` necesario para servir el índice público;
- `release_metadata.json` saneado;
- `release_manifest.json` con SHA256 por archivo.

No empaqueta:

- PDFs fuente;
- Markdown normalizado;
- canonical textual;
- corpus UNAM;
- corpus PRODECON;
- bases de datos;
- secretos;
- claves;
- pesos de modelos.

## Auditoría

Se bloquea si existe:

- identidad documental UNAM/PRODECON en archivos JSON/JSONL;
- secreto aparente;
- ruta privada absoluta Windows/POSIX;
- PDF, Markdown, DB, claves o pesos de modelos;
- symlink;
- divergencia de hash al copiar;
- contenido ZIP diferente al manifest.

El ZIP usa orden estable, timestamp fijo y permisos normalizados para que dos
construcciones desde los mismos bytes produzcan el mismo SHA256.

## Semántica de aceptación

Aunque el candidato técnico sea correcto, los gates permanecen:

- `candidate_only=True`
- `publication_legal_acceptance=False`
- `temporal_validity_complete=False`
- `public_release_allowed=False`
- `git_push_allowed=False`
- `github_release_allowed=False`
- `render_deploy_allowed=False`

## Implementación

1. Expandir el patch.
2. Ejecutar prueba específica, Ruff, mypy y pytest completo.
3. Ejecutar:
   `python -m scripts.build_public_release_candidate_19i18m`
4. Conservar `dist/public_release_candidate_19i18m` si aparece un error.
