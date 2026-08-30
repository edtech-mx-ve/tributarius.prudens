# Sprint 19I.18S-r16F — Explanation Integrity Boundary

## Objetivo

Crear un contrato explícito y auditable entre la evidencia jurídica y cualquier
capa de explicación presente o futura, antes de integrar Llama.

## Diseño

La capa `public_explanation_integrity_19s_r16f` clasifica la explicación
pública sin modificar su contenido y añade metadata:

- `policy=evidence_bound_fail_closed`;
- `status`;
- `evidence_count`;
- `applicable_normative_ref_count`;
- `requires_human_review`;
- `llm_authority=none`.

## Estados

- `not_generated`;
- `grounded_applicable_norm`;
- `evidence_only_review_required`;
- `review_required_without_evidence`;
- `evidence_present_no_applicability_claim`;
- `ungrounded`.

## Invariantes

r16F no modifica:

- recuperación;
- ranking;
- normativa aplicable;
- política temporal;
- reglas;
- cálculos;
- `requires_human_review`;
- texto de la explicación.

Llama no se conecta en este incremento y no obtiene autoridad normativa.

## Criterios de aceptación

1. Tests r16F verdes.
2. Ruff y mypy verdes.
3. `git diff --check` limpio.
4. Smoke HTTP expone `policy=evidence_bound_fail_closed`.
5. `llm_authority=none`.
6. E2E-01..06 r16D permanece verde.
