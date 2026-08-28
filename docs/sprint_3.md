# Sprint 3 — Chunking jurídico estructural

## Objetivo

Transformar el Markdown normalizado del Sprint 1 en unidades recuperables
jurídicamente coherentes y trazables, sin realizar todavía embeddings.

## Jerarquía operativa

`título → capítulo → sección → artículo → fracción → inciso → párrafo`

Cada chunk conserva:

- `chunk_id` determinista.
- `document_id`.
- `source_type`.
- archivo fuente.
- `source_sha256`.
- índice de chunk.
- tipo jurídico.
- identificador jurídico cuando existe.
- página inicial/final.
- jerarquía jurídica acumulada.
- año fiscal y versión, cuando esos datos estén disponibles.

## Reglas implementadas

- Los marcadores `<!-- page:n -->` del Sprint 1 se usan para trazabilidad.
- Los encabezados sintéticos `## Página n` no se convierten en chunks.
- Los títulos/capítulos/secciones/artículos se reconocen por patrones conservadores.
- Las fracciones (`I.`, `II.`, `1.`) e incisos (`a)`, `b)`) se detectan solo
  dentro de un artículo.
- No se inventan artículos, fracciones ni metadatos ausentes.
- Los chunks demasiado largos se dividen de forma determinista.
- No se sobrescriben artefactos salvo con `--overwrite`.

## Formato de salida

JSON Lines (`.jsonl`), un objeto `LegalChunk` por línea.

## Ejecución

```powershell
python -m scripts.chunk_legal_document `
  --markdown ".\knowledge\normalized\normativa\documento.md" `
  --metadata ".\knowledge\metadata\documento.json" `
  --output ".\knowledge\chunks\normativa\documento.jsonl"
```

## Criterios de aceptación

1. Preserva páginas.
2. Preserva jerarquía.
3. Produce IDs deterministas.
4. Distingue normativa/jurisprudencia por `source_type`.
5. Rechaza entradas inválidas.
6. Evita sobrescritura silenciosa.
7. Produce JSONL válido y auditable.
8. Mantiene compatibilidad con Sprint 1 y Sprint 2.
9. No ejecuta embeddings ni FAISS.

## Limitaciones

- El reconocimiento jurídico es conservador y basado en patrones.
- La estructura exacta puede variar entre leyes, reglas, tesis y materiales académicos.
- Jurisprudencia especializada tendrá un pipeline propio en Sprint 17.
- El tamaño máximo se expresa en caracteres, no en tokens del LLM.
- Materia, vigencia y versión no se infieren del texto en este sprint.
