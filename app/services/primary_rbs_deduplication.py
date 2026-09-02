from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_rbs_deduplication import PrimaryRBSDeduplicationMap
from app.domain.primary_rbs_source_relations import PrimaryRBSRelationExtraction


class PrimaryRBSDeduplicationError(RuntimeError):
    """Error controlado del mapa de deduplicación B.5."""


def load_primary_rbs_deduplication_map(path: Path) -> PrimaryRBSDeduplicationMap:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSDeduplicationError(
            f"No existe el mapa de deduplicación RBS: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryRBSDeduplicationMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryRBSDeduplicationError(
            "El mapa de deduplicación B.5 no es válido."
        ) from exc


def validate_primary_rbs_deduplication(
    deduplication: PrimaryRBSDeduplicationMap,
    prodecon: PrimaryRBSRelationExtraction,
    unam: PrimaryRBSRelationExtraction,
) -> None:
    """Comprueba cobertura exacta de las 38 relaciones fuente y preservación de procedencia."""
    source_relations = {
        relation.relation_id: relation
        for relation in [*prodecon.relations, *unam.relations]
    }
    if deduplication.source_relation_count != len(source_relations):
        raise PrimaryRBSDeduplicationError(
            "source_relation_count no coincide con las relaciones B.3+B.4."
        )

    referenced_ids = [
        source_id
        for relation in deduplication.relations
        for source_id in relation.source_relation_ids
    ]
    if set(referenced_ids) != set(source_relations):
        missing = sorted(set(source_relations) - set(referenced_ids))
        extra = sorted(set(referenced_ids) - set(source_relations))
        raise PrimaryRBSDeduplicationError(
            f"B.5 no cubre exactamente las relaciones fuente; missing={missing}, extra={extra}"
        )
    if len(referenced_ids) != len(set(referenced_ids)):
        raise PrimaryRBSDeduplicationError(
            "Una relación fuente fue asignada a más de una relación deduplicada."
        )

    for relation in deduplication.relations:
        sources = [source_relations[source_id] for source_id in relation.source_relation_ids]
        derived_entries = {source.source_entry_id for source in sources}
        if set(relation.primary_entry_ids) != derived_entries:
            raise PrimaryRBSDeduplicationError(
                f"{relation.canonical_id} no preserva las entradas primarias de origen."
            )

        derived_families = {
            family
            for source in sources
            for family in source.rbs_families
        }
        if not set(relation.rbs_families) <= derived_families:
            raise PrimaryRBSDeduplicationError(
                f"{relation.canonical_id} introduce familias RBS no sustentadas."
            )

        derived_normative = {
            source
            for relation_source in sources
            for source in relation_source.candidate_normative_sources
        }
        if not set(relation.candidate_normative_sources) <= derived_normative:
            raise PrimaryRBSDeduplicationError(
                f"{relation.canonical_id} introduce candidatos normativos no sustentados."
            )

        if any(source.relation_id.startswith("P-REL-") for source in sources) and any(
            source.relation_id.startswith("U-REL-") for source in sources
        ):
            continue

        # No todas las relaciones necesitan tener equivalente en ambas fuentes;
        # la deduplicación conserva también conceptos exclusivos.
