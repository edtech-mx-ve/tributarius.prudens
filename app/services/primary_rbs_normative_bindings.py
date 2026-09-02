from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_rbs_deduplication import PrimaryRBSDeduplicationMap
from app.domain.primary_rbs_normative_bindings import PrimaryRBSNormativeBindingMap


class PrimaryRBSNormativeBindingError(RuntimeError):
    """Error controlado del mapa normativo B.6."""


def load_primary_rbs_normative_binding_map(
    path: Path,
) -> PrimaryRBSNormativeBindingMap:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSNormativeBindingError(
            f"No existe el mapa de vínculos normativos B.6: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryRBSNormativeBindingMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryRBSNormativeBindingError(
            "El mapa de vínculos normativos B.6 no es válido."
        ) from exc


def validate_primary_rbs_normative_bindings(
    bindings: PrimaryRBSNormativeBindingMap,
    deduplication: PrimaryRBSDeduplicationMap,
    allowed_normative_source_ids: set[str],
) -> None:
    """Valida cobertura B.5 y cierre contra el corpus normativo interno."""
    relations = {relation.canonical_id: relation for relation in deduplication.relations}
    bound_relations = {binding.relation_id for binding in bindings.bindings}

    if bound_relations != set(relations):
        raise PrimaryRBSNormativeBindingError(
            "B.6 debe cubrir exactamente todas las relaciones consolidadas B.5."
        )

    for binding in bindings.bindings:
        relation = relations[binding.relation_id]

        if not set(binding.rule_family_ids) <= set(relation.rbs_families):
            raise PrimaryRBSNormativeBindingError(
                f"{binding.binding_id} introduce familias RBS no sustentadas por B.5."
            )

        if not set(binding.normative_source_ids) <= set(
            relation.candidate_normative_sources
        ):
            raise PrimaryRBSNormativeBindingError(
                f"{binding.binding_id} amplía indebidamente los candidatos B.5."
            )

        if not set(binding.normative_source_ids) <= allowed_normative_source_ids:
            raise PrimaryRBSNormativeBindingError(
                f"{binding.binding_id} sale del corpus normativo interno permitido."
            )

        for exact_ref in binding.exact_normative_refs:
            source_id = exact_ref.split(":", 1)[0]
            if source_id not in binding.normative_source_ids:
                raise PrimaryRBSNormativeBindingError(
                    f"{binding.binding_id} contiene una referencia exacta "
                    "fuera de sus fuentes normativas."
                )
            if source_id not in allowed_normative_source_ids:
                raise PrimaryRBSNormativeBindingError(
                    f"{binding.binding_id} contiene una referencia exacta "
                    "fuera del corpus normativo interno."
                )
