# Sprint 19I.18S-r16E — Public Evidence Quality

## Objetivo

Mejorar la calidad de la evidencia visible sin modificar recuperación, ranking,
aplicabilidad normativa, reglas, cálculos ni decisiones de revisión humana.

## Alcance

- deduplicación pública por `ref_id`, preservando la primera aparición;
- eliminación de tarjetas de evidencia estructuralmente vacías;
- conservación de evidencia sin `ref_id` cuando contiene identidad o contenido;
- integración en el middleware público antes de normalizar Unicode;
- smoke HTTP para medir duplicados y tarjetas vacías.

## Invariantes

Este incremento no altera:

- `applicable_normative_refs`;
- `requires_human_review`;
- puntuaciones de recuperación;
- orden de primeras apariciones;
- contenido de la primera evidencia;
- runtime RAG o backend lexical CPU;
- política temporal.

## Criterios de aceptación

1. Tests r16E verdes.
2. Ruff y mypy verdes.
3. `git diff --check` limpio.
4. Smoke local: `duplicate_ref_ids=0` y `empty_cards=0`.
5. E2E-01..06 r16D continúa verde.
