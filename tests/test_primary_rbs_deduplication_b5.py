from pathlib import Path

from app.services.primary_rbs_deduplication import (
    load_primary_rbs_deduplication_map,
    validate_primary_rbs_deduplication,
)
from app.services.primary_rbs_source_relations import load_primary_rbs_relation_extraction

ROOT = Path(__file__).resolve().parents[1]
DEDUP_PATH = ROOT / "app" / "resources" / "primary_rbs_deduplication_map.json"
PRODECON_PATH = ROOT / "app" / "resources" / "prodecon_rbs_relations.json"
UNAM_PATH = ROOT / "app" / "resources" / "unam_rbs_relations.json"


def test_b5_deduplicates_both_primary_sources() -> None:
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)

    assert dedup.source_relation_count == 38
    assert dedup.deduplicated_relation_count < dedup.source_relation_count
    assert dedup.preserves_source_provenance is True


def test_b5_covers_every_b3_and_b4_relation_exactly_once() -> None:
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)
    prodecon = load_primary_rbs_relation_extraction(PRODECON_PATH)
    unam = load_primary_rbs_relation_extraction(UNAM_PATH)

    validate_primary_rbs_deduplication(dedup, prodecon, unam)


def test_b5_contains_cross_source_consolidations() -> None:
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)

    cross_source = [
        relation
        for relation in dedup.relations
        if any(source.startswith("P-REL-") for source in relation.source_relation_ids)
        and any(source.startswith("U-REL-") for source in relation.source_relation_ids)
    ]

    assert len(cross_source) >= 10


def test_b5_preserves_non_determinative_boundary() -> None:
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)

    assert all(relation.requires_normative_validation for relation in dedup.relations)
    assert all(not relation.can_control_legal_decision for relation in dedup.relations)


def test_b5_preserves_rif_temporality() -> None:
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)
    temporal = next(
        relation
        for relation in dedup.relations
        if "P-REL-023" in relation.source_relation_ids
    )

    assert "P-REL-024" in temporal.source_relation_ids
    assert "R-TEM" in temporal.rbs_families
    assert "REL-TEM-APL" in temporal.legal_relation_ids
