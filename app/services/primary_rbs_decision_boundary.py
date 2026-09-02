from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_rbs_decision_boundary import PrimaryRBSDecisionBoundaryMap
from app.domain.primary_rbs_deduplication import PrimaryRBSDeduplicationMap
from app.domain.primary_rbs_normative_bindings import PrimaryRBSNormativeBindingMap


class PrimaryRBSDecisionBoundaryError(RuntimeError):
    """Error controlado del límite orientación/determinación B.7."""


def load_primary_rbs_decision_boundary_map(
    path: Path,
) -> PrimaryRBSDecisionBoundaryMap:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSDecisionBoundaryError(
            f"No existe el mapa B.7 orientación/determinación: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryRBSDecisionBoundaryMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryRBSDecisionBoundaryError(
            "El mapa B.7 orientación/determinación no es válido."
        ) from exc


def validate_primary_rbs_decision_boundaries(
    boundary_map: PrimaryRBSDecisionBoundaryMap,
    deduplication: PrimaryRBSDeduplicationMap,
    bindings: PrimaryRBSNormativeBindingMap,
) -> None:
    """Valida cobertura exacta y que B.7 no eleve heurística a autoridad jurídica."""
    relations = {relation.canonical_id: relation for relation in deduplication.relations}
    binding_by_relation = {
        binding.relation_id: binding for binding in bindings.bindings
    }

    if {boundary.relation_id for boundary in boundary_map.boundaries} != set(relations):
        raise PrimaryRBSDecisionBoundaryError(
            "B.7 debe clasificar exactamente todas las relaciones B.5."
        )

    for boundary in boundary_map.boundaries:
        binding = binding_by_relation.get(boundary.relation_id)
        if binding is None:
            raise PrimaryRBSDecisionBoundaryError(
                f"{boundary.relation_id} carece de binding B.6."
            )
        if boundary.binding_id != binding.binding_id:
            raise PrimaryRBSDecisionBoundaryError(
                f"{boundary.boundary_id} no corresponde al binding B.6 esperado."
            )
        relation = relations[boundary.relation_id]
        if set(boundary.orientation_sources) != set(relation.primary_entry_ids):
            raise PrimaryRBSDecisionBoundaryError(
                f"{boundary.boundary_id} no preserva las fuentes primarias de B.5."
            )
        if set(boundary.normative_source_ids) != set(binding.normative_source_ids):
            raise PrimaryRBSDecisionBoundaryError(
                f"{boundary.boundary_id} altera las fuentes normativas de B.6."
            )
        if set(boundary.exact_normative_refs) != set(binding.exact_normative_refs):
            raise PrimaryRBSDecisionBoundaryError(
                f"{boundary.boundary_id} altera las referencias exactas de B.6."
            )

        has_exact_refs = bool(binding.exact_normative_refs)
        expected_role = (
            "determination_candidate" if has_exact_refs else "orientation"
        )
        if boundary.role.value != expected_role:
            raise PrimaryRBSDecisionBoundaryError(
                f"{boundary.boundary_id} tiene un rol incompatible con B.6."
            )
