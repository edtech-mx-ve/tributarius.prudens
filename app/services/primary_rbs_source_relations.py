from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_legal_knowledge import PrimaryKnowledgeMap
from app.domain.primary_rbs_families import PrimaryRBSFamilyRegistry
from app.domain.primary_rbs_source_relations import (
    PrimaryRBSRelationExtraction,
    PrimaryRelationSource,
)


class PrimaryRBSRelationExtractionError(RuntimeError):
    """Error controlado de extracción de relaciones RBS primarias."""


def load_primary_rbs_relation_extraction(path: Path) -> PrimaryRBSRelationExtraction:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSRelationExtractionError(
            f"No existe la extracción de relaciones RBS: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryRBSRelationExtraction.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryRBSRelationExtractionError(
            "La extracción de relaciones RBS primarias no es válida."
        ) from exc


def validate_primary_rbs_relation_extraction(
    extraction: PrimaryRBSRelationExtraction,
    knowledge_map: PrimaryKnowledgeMap,
    family_registry: PrimaryRBSFamilyRegistry,
) -> None:
    """Valida cierre de fuente, familias y candidatos normativos contra Bloques A/B.2."""
    entries = {entry.entry_id: entry for entry in knowledge_map.entries}
    family_ids = {family.family_id for family in family_registry.families}

    expected_entries = {
        entry.entry_id
        for entry in knowledge_map.entries
        if entry.manual.value == extraction.source.value
    }
    used_entries = {relation.source_entry_id for relation in extraction.relations}
    if used_entries != expected_entries:
        raise PrimaryRBSRelationExtractionError(
            "La extracción no cubre exactamente las entradas de la fuente primaria."
        )
    if extraction.source_entry_count != len(expected_entries):
        raise PrimaryRBSRelationExtractionError(
            "source_entry_count no coincide con la fuente primaria."
        )

    for relation in extraction.relations:
        entry = entries.get(relation.source_entry_id)
        if entry is None:
            raise PrimaryRBSRelationExtractionError(
                f"Entrada primaria desconocida: {relation.source_entry_id}"
            )
        unknown_families = set(relation.rbs_families) - family_ids
        if unknown_families:
            raise PrimaryRBSRelationExtractionError(
                f"Familias RBS desconocidas: {sorted(unknown_families)}"
            )
        if not set(relation.rbs_families) <= set(entry.rbs_families):
            raise PrimaryRBSRelationExtractionError(
                f"{relation.relation_id} usa familias no sustentadas por "
                f"{relation.source_entry_id}."
            )
        if not set(relation.candidate_normative_sources) <= set(
            entry.candidate_normative_sources
        ):
            raise PrimaryRBSRelationExtractionError(
                f"{relation.relation_id} amplía indebidamente candidatos normativos."
            )

    if extraction.source == PrimaryRelationSource.PRODECON and len(expected_entries) != 12:
        raise PrimaryRBSRelationExtractionError(
            "B.3 exige exactamente las 12 entradas PRODECON."
        )
